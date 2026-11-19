import hashlib
import hmac
import io
import json
import os
import threading
import time
import uuid
import warnings
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image
from pypdf import PdfReader
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .auth import AuthError, OIDCVerifier
from .crypto import Cipher
from .engine import evaluate, relevant_fields
from .graph import Neo4jGraph, retrieve_module1
from .investigation import Investigator, build_bank_client, load_procedures, public_result
from .models import CheckInput, Feedback, InvestigationInput, LabExperiment
from .metrics import Metrics, MetricsMiddleware
from .providers import Gemini, Qwen, Source, extract_demo
from .rag import policy_bundle
from .retrieval import (
    DEFAULT_QUERY,
    HybridRetriever,
    RetrievalSettings,
    build_embedder,
    build_retriever,
    chunk_policy,
)
from .retrieval_eval import load_questions, run_experiment
from .scanning import ScanUnavailable, build_scanner
from .security import suspicious
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 5 * 1024 * 1024
MAX_BODY = MAX_FILE + 64 * 1024
KINDS = {"business_license", "representative_id", "bank_confirmation"}
DEMO_TOKENS = {
    "demo-checker-token": {"user": "checker-demo", "tenant": "pvcb", "role": "checker"},
    "demo-maker-token": {"user": "maker-demo", "tenant": "pvcb", "role": "maker"},
    "demo-viewer-token": {"user": "viewer-demo", "tenant": "pvcb", "role": "viewer"},
}


class Boundary:
    """Bound actual streamed request bytes before multipart/JSON parsing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, total = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            total += len(message.get("body", b""))
            if total > MAX_BODY:
                return await JSONResponse({"detail": "Request too large"}, 413)(
                    scope, receive, send
                )
            chunks.append(message.get("body", b""))
            if not message.get("more_body"):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {
                    "type": "http.request",
                    "body": b"".join(chunks),
                    "more_body": False,
                }
            return await receive()

        async def secured(message):
            if message["type"] == "http.response.start":
                message["headers"] += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                    (
                        b"content-security-policy",
                        b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; frame-src blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                    ),
                ]
            await send(message)

        await self.app(scope, replay, secured)


def inspect_source(data: bytes, filename: str, mode: str) -> Source:
    suffix = Path(filename).suffix.lower()
    if not data or len(data) > MAX_FILE:
        raise ValueError("Empty file or over 5 MiB")
    if suffix == ".txt" and mode == "demo":
        text = data.decode("utf-8")
        if len(text) > 20000 or "\x00" in text:
            raise ValueError("Invalid demo text")
        return Source(data, "text/plain", 1)
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 20:
            raise ValueError("Encrypted PDF or page limit exceeded")
        if any(
            key in reader.trailer["/Root"] for key in ["/OpenAction", "/AA", "/Names"]
        ):
            raise ValueError("Active or embedded PDF content is not accepted")
        return Source(data, "application/pdf", len(reader.pages))
    if suffix in {".jpg", ".jpeg", ".png"}:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            expected = "PNG" if suffix == ".png" else "JPEG"
            if image.format != expected or image.width * image.height > 20_000_000:
                raise ValueError("Invalid image or too many pixels")
            image.verify()
        return Source(data, "image/png" if expected == "PNG" else "image/jpeg", 1)
    raise ValueError("Allowed: PDF/JPEG/PNG; synthetic TXT in demo mode")


def create_app(data_dir=None, mode=None):
    mode = mode or os.getenv("AI_MODE", "demo")
    if mode not in {"demo", "gemini", "qwen"}:
        raise ValueError("AI_MODE must be demo, gemini or qwen")
    production = os.getenv("APP_ENV") == "production"
    auth_mode = os.getenv("AUTH_MODE", "tokens").casefold()
    if auth_mode not in {"tokens", "oidc"}:
        raise ValueError("AUTH_MODE must be tokens or oidc")
    oidc = OIDCVerifier.from_env() if auth_mode == "oidc" else None
    cipher = Cipher.from_env()
    scanner = build_scanner()
    tokens = json.loads(os.getenv("TOKENS_JSON") or json.dumps(DEMO_TOKENS))
    if not tokens or any(
        not isinstance(t, str)
        or not isinstance(p, dict)
        or set(p) != {"user", "tenant", "role"}
        or not all(isinstance(v, str) and v for v in p.values())
        or p["role"] not in {"maker", "checker", "viewer"}
        for t, p in tokens.items()
    ):
        raise ValueError("Invalid server-side principal configuration")
    if production and auth_mode == "tokens" and (
        any(len(t) < 32 or t.startswith("demo-") for t in tokens)
    ):
        raise ValueError(
            "Production requires explicit strong tokens or AUTH_MODE=oidc"
        )
    if production and not cipher.enabled:
        raise ValueError("Production requires DATA_ENCRYPTION_KEY for data at rest")
    if production and scanner is None:
        raise ValueError("Production requires MALWARE_SCAN=clamd for uploads")
    graph_mode = os.getenv("GRAPH_BACKEND", "local").casefold()
    if graph_mode not in {"local", "neo4j"}:
        raise ValueError("GRAPH_BACKEND must be local or neo4j")
    graph_backend = None
    if graph_mode == "neo4j":
        graph_backend = Neo4jGraph(
            os.getenv("NEO4J_URI", ""),
            os.getenv("NEO4J_USERNAME", ""),
            os.getenv("NEO4J_PASSWORD", ""),
            os.getenv("GRAPH_HMAC_KEY", ""),
            os.getenv("NEO4J_DATABASE", "neo4j"),
        )
    store = Store(data_dir or os.getenv("DATA_DIR", str(ROOT / "runtime")), cipher)
    store.seed(ROOT / "samples/applications.json")

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if graph_backend:
            graph_backend.close()
        app.state.investigator.bank.close()

    app = FastAPI(
        title="VietPay MMS AI Document Checker",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )  # /openapi.json remains available for integration.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv(
            "ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
        ).split(","),
    )
    app.add_middleware(Boundary)
    metrics = Metrics()
    app.add_middleware(MetricsMiddleware, metrics=metrics)
    app.state.metrics, app.state.scanner = metrics, scanner
    app.state.store, app.state.mode = store, mode
    app.state.graph_backend = graph_backend
    app.state.retriever = build_retriever()

    def model_name():
        if mode == "gemini":
            return os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        if mode == "qwen":
            return os.getenv("QWEN_MODEL", "qwen3.5:9b")
        return None

    def provider_factory():
        if mode == "qwen":
            return Qwen(
                os.getenv("QWEN_BASE_URL", "http://127.0.0.1:11434/v1"),
                model_name(),
                os.getenv("QWEN_API_KEY", ""),
                float(os.getenv("QWEN_TIMEOUT", "120")),
                os.getenv("QWEN_REASONING_EFFORT", "none"),
            )
        return Gemini(os.getenv("GEMINI_API_KEY", ""), model_name())

    app.state.provider_factory = provider_factory
    bank = build_bank_client()
    app.state.investigator = Investigator(
        bank, lambda: app.state.provider_factory(), mode
    )
    limiter, limit_lock = {}, threading.Lock()
    capacity = threading.BoundedSemaphore(2)
    bearer = HTTPBearer(auto_error=False)

    def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials and oidc:
            try:
                return oidc.principal(credentials.credentials)
            except AuthError as error:
                headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else None
                raise HTTPException(error.status, str(error), headers=headers) from None
        if credentials:
            for token, account in tokens.items():
                if hmac.compare_digest(
                    credentials.credentials.encode(), token.encode()
                ):
                    return account
        raise HTTPException(
            401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
        )

    def write_access(p):
        if p["role"] not in {"maker", "checker"}:
            raise HTTPException(403, "Maker or checker role required")
        # In-process actor limit; gateway must impose distributed connection/body limits.
        key = (p["tenant"], p["user"])
        with limit_lock:
            now = time.monotonic()
            recent = [t for t in limiter.get(key, []) if now - t < 60]
            if len(recent) >= 20:
                raise HTTPException(
                    429, "Try again later", headers={"Retry-After": "60"}
                )
            limiter[key] = recent + [now]

    def application(app_id, p):
        result = store.application(app_id, p["tenant"])
        if not result:
            raise HTTPException(404, "Application not found")
        return result

    def checked(check_id, p):
        result = store.check(check_id, p["tenant"])
        if not result:
            raise HTTPException(404, "Check not found")
        current = application(result["application_id"], p)
        result["stale"] = current["revision"] != result["application_revision"]
        return result

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "static/index.html")

    @app.get("/assets/{name}", include_in_schema=False)
    def assets(name: str):
        if name not in {"app.js", "style.css", "lab.js", "investigate.js"}:
            raise HTTPException(404)
        return FileResponse(ROOT / "static" / name)

    @app.get("/healthz")
    def health():
        with store.db() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "mode": mode, "model": model_name(), "auth": auth_mode}

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        # Disabled unless METRICS_TOKEN is set; scrape with that bearer token.
        expected = os.getenv("METRICS_TOKEN", "")
        if not expected:
            raise HTTPException(404)
        if not credentials or not hmac.compare_digest(
            credentials.credentials.encode(), expected.encode()
        ):
            raise HTTPException(
                401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
            )
        return Response(metrics.render(), media_type="text/plain; version=0.0.4")

    @app.get("/api/applications")
    def list_applications(p=Depends(principal)):
        return store.applications(p["tenant"])

    @app.get("/api/applications/{app_id}")
    def get_application(app_id: str, p=Depends(principal)):
        result = application(app_id, p)
        return {**result, "documents": [meta for meta, _ in store.documents(app_id)]}

    @app.post("/api/applications/{app_id}/documents", status_code=201)
    def upload(
        app_id: str,
        kind: str = Form(...),
        file: UploadFile = File(...),
        p=Depends(principal),
    ):
        write_access(p)
        application(app_id, p)
        if kind not in KINDS:
            raise HTTPException(422, "Unknown document kind")
        data = file.file.read(MAX_FILE + 1)
        try:
            source = inspect_source(data, file.filename or "", mode)
        except Exception:
            metrics.inc("mms_uploads_rejected_total", reason="invalid")
            raise HTTPException(
                422, "Invalid, unsupported, encrypted or oversized document"
            ) from None
        if mode == "demo" and source.mime != "text/plain":
            metrics.inc("mms_uploads_rejected_total", reason="demo_type")
            raise HTTPException(
                422, "Demo reads synthetic TXT only; set AI_MODE=gemini for PDF/images"
            )
        scan = None
        if scanner:
            try:
                scan = scanner.scan(data)
            except ScanUnavailable:
                metrics.inc("mms_uploads_rejected_total", reason="scanner_unavailable")
                raise HTTPException(
                    503, "Malware scanner unavailable; upload not stored"
                ) from None
            if not scan.clean:
                metrics.inc("mms_uploads_rejected_total", reason="malware")
                store.audit(
                    p,
                    "upload_rejected_malware",
                    app_id,
                    {"signature": scan.signature, "sha256": hashlib.sha256(data).hexdigest()},
                )
                raise HTTPException(422, "File rejected by malware scan")
        meta = {
            "id": str(uuid.uuid4()),
            "kind": kind,
            "mime": source.mime,
            "pages": source.pages,
            "verification": "pending",
            "verified_version": 0,
            "sha256": hashlib.sha256(data).hexdigest(),
            "malware_scan": scan.engine if scan else "not_configured",
        }
        meta = store.put_document(app_id, meta, data)
        store.audit(
            p,
            "document_uploaded",
            app_id,
            {"document_id": meta["id"], "version": meta["version"]},
        )
        return meta

    @app.post("/api/applications/{app_id}/checks", status_code=201)
    def run_check(app_id: str, body: CheckInput, p=Depends(principal)):
        write_access(p)
        record = application(app_id, p)
        if not capacity.acquire(blocking=False):
            raise HTTPException(429, "Checker busy; try again later")
        provider, started = None, time.perf_counter()
        try:
            today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
            try:
                rules, md, digest = policy_bundle(p["tenant"], today)
            except ValueError:
                raise HTTPException(
                    409, "Applicable policy unavailable; manual review required"
                ) from None
            if mode in {"gemini", "qwen"}:
                try:
                    provider = app.state.provider_factory()
                except Exception:
                    raise HTTPException(
                        503, "AI model unavailable; check server configuration"
                    ) from None
            documents = store.documents(app_id)
            extracted, events = {}, []
            for meta, data in documents:
                try:
                    source = Source(data, meta["mime"], meta["pages"])
                    if source.mime == "text/plain" and suspicious(data.decode("utf-8")):
                        events.append(
                            {
                                "stage": "input",
                                "document_id": meta["id"],
                                "status": "suspicious_document_content",
                            }
                        )
                    result = (
                        provider.extract(source, relevant_fields(meta["kind"], rules))
                        if provider
                        else extract_demo(source)
                    )
                    if any(f.page > meta["pages"] for f in result.facts):
                        raise ValueError("Page outside document")
                    if source.mime == "text/plain" and any(
                        f.quote not in data.decode("utf-8") for f in result.facts
                    ):
                        raise ValueError("Unverified quote")
                    extracted[meta["id"]] = result
                except Exception:
                    events.append(
                        {
                            "stage": "extraction",
                            "document_id": meta["id"],
                            "status": "failed",
                        }
                    )
            findings = evaluate(
                record, [m for m, _ in documents], extracted, rules, today, mode
            )
            query = body.question
            if suspicious(body.question):
                # Question is never forwarded to the generative model or used as
                # policy authority. A suspicious question does not steer retrieval.
                events.append(
                    {"stage": "input", "status": "suspicious_question_ignored"}
                )
                query = DEFAULT_QUERY
            sections, retrieval_trace = app.state.retriever.search(
                md,
                rules,
                p["tenant"],
                today.isoformat(),
                query,
                set(rules["rules"].values()),
            )
            if retrieval_trace["status"]:
                events.append({"stage": "retrieval", "status": retrieval_trace["status"]})
            graph_result, sections, graph_warning = retrieve_module1(
                record,
                [m for m, _ in documents],
                findings,
                rules,
                sections,
                app.state.graph_backend,
            )
            if graph_warning:
                events.append({"stage": "graph", "status": graph_warning})
            notes = [{"finding_id": f.id, "text": f.message} for f in findings]
            explanation_mode = "deterministic"
            if provider and findings:
                try:
                    notes = provider.explain(
                        findings, sections, graph_result["evidence"]
                    )
                    explanation_mode = mode
                except Exception:
                    events.append({"stage": "explanation", "status": "fallback"})
            result = {
                "id": str(uuid.uuid4()),
                "application_id": app_id,
                "tenant": p["tenant"],
                "application_revision": record["revision"],
                "application_snapshot": record,
                "created_at": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
                "review_date": today.isoformat(),
                "status": "completed",
                "mode": mode,
                "model": model_name() if provider else None,
                "explanation_mode": explanation_mode,
                "summary": "Cần bổ sung hoặc kiểm tra lại."
                if findings
                else "Không phát hiện lỗi trong phạm vi quy tắc demo; nhân viên vẫn quyết định duyệt.",
                "approval": "human_decision_required",
                "policy_id": rules["policy_id"],
                "policy_version": rules["version"],
                "policy_sha256": digest,
                "policy_sections": sections,
                "policy_retrieval": retrieval_trace,
                "graph_retrieval": graph_result,
                "findings": [f.model_dump() for f in findings],
                "notes": notes,
                "events": events,
                "extractions": {k: v.model_dump() for k, v in extracted.items()},
                "document_manifest": [
                    {**m, "sha256": hashlib.sha256(d).hexdigest()} for m, d in documents
                ],
            }
            store.save_check(result, documents)
            metrics.inc("mms_checks_total", mode=mode)
            metrics.observe("mms_model_seconds", time.perf_counter() - started, mode=mode)
            for finding in findings:
                metrics.inc("mms_findings_total", code=finding.code)
            for event in events:
                metrics.inc(
                    "mms_check_events_total", stage=event["stage"], status=event["status"]
                )
            store.audit(
                p,
                "check_completed",
                result["id"],
                {"finding_count": len(findings), "mode": mode, "policy_sha256": digest},
            )
            return checked(result["id"], p)
        finally:
            if provider:
                provider.close()
            capacity.release()

    @app.get("/api/checks/{check_id}")
    def get_check(check_id: str, p=Depends(principal)):
        return checked(check_id, p)

    @app.get("/api/checks/{check_id}/evidence/{finding_id}")
    def get_evidence(check_id: str, finding_id: str, p=Depends(principal)):
        result = checked(check_id, p)
        finding = next((f for f in result["findings"] if f["id"] == finding_id), None)
        if not finding:
            raise HTTPException(404, "Evidence not found")
        meta = next(
            (
                m
                for m in result["document_manifest"]
                if m["id"] == finding["document_id"]
            ),
            None,
        )
        store.audit(p, "evidence_viewed", check_id, {"finding_id": finding_id})
        return {
            "finding": finding,
            "document": meta,
            "application_snapshot": result["application_snapshot"],
            "policy": next(
                s for s in result["policy_sections"] if s["rule"] == finding["rule"]
            ),
            "graph": next(
                (
                    row
                    for row in result.get("graph_retrieval", {}).get("evidence", [])
                    if row["finding_id"] == finding_id
                ),
                None,
            ),
            "original_url": f"/api/checks/{check_id}/documents/{meta['id']}"
            if meta
            else None,
            "stale": result["stale"],
        }

    @app.get("/api/checks/{check_id}/documents/{doc_id}")
    def original(check_id: str, doc_id: str, p=Depends(principal)):
        checked(check_id, p)
        source = store.evidence(check_id, doc_id)
        if not source:
            raise HTTPException(404, "Document not found")
        meta, data = source
        store.audit(p, "document_downloaded", check_id, {"document_id": doc_id})
        extension = {
            "text/plain": "txt",
            "application/pdf": "pdf",
            "image/png": "png",
            "image/jpeg": "jpg",
        }[meta["mime"]]
        return Response(
            data,
            media_type=meta["mime"],
            headers={
                "Content-Disposition": f'attachment; filename="source.{extension}"'
            },
        )

    @app.post("/api/checks/{check_id}/feedback", status_code=201)
    def feedback(check_id: str, body: Feedback, p=Depends(principal)):
        if p["role"] != "checker":
            raise HTTPException(403, "Checker role required")
        write_access(p)
        result = checked(check_id, p)
        if result["stale"]:
            raise HTTPException(409, "Document changed; run a new check")
        if body.finding_id not in {f["id"] for f in result["findings"]}:
            raise HTTPException(422, "Unknown finding")
        store.audit(p, "feedback_recorded", check_id, body.model_dump())
        return {
            "saved": True,
            "approval": "unchanged",
            "automatically_trains_model": False,
        }

    # ---- Transaction and payout investigation (assistant features 2 and 3) ----

    def actor_limit(p):
        # Same per-actor budget as writes; viewers may investigate (read-only).
        write_access({**p, "role": "maker"})

    @app.get("/investigate", include_in_schema=False)
    def investigate_page():
        return FileResponse(ROOT / "static/investigate.html")

    @app.post("/api/investigations", status_code=201)
    def investigate(body: InvestigationInput, p=Depends(principal)):
        actor_limit(p)
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        try:
            procedures, procedures_sha = load_procedures(p["tenant"], today)
        except ValueError:
            raise HTTPException(409, "Applicable handling procedure unavailable") from None
        if not capacity.acquire(blocking=False):
            raise HTTPException(429, "Checker busy; try again later")
        try:
            state = app.state.investigator.run(p, body.transaction_id, procedures)
        finally:
            capacity.release()
        if not state.get("transaction"):
            unavailable = any(e["status"] == "source_unavailable" for e in state["events"])
            metrics.inc("mms_investigations_total", outcome="source_unavailable" if unavailable else "not_found")
            store.audit(p, "transaction_lookup_failed", body.transaction_id, {"unavailable": unavailable})
            if unavailable:
                raise HTTPException(503, "Bank transaction service unavailable")
            raise HTTPException(404, "Transaction not found")
        record = {
            "id": str(uuid.uuid4()),
            "tenant": p["tenant"],
            "actor": p["user"],
            "created_at": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
            "transaction_id": body.transaction_id,
            "merchant_id": state["transaction"]["merchant_id"],
            "question": body.question,
            "bank_source": app.state.investigator.bank.name,
            "procedure_id": procedures["policy_id"],
            "procedure_version": procedures["version"],
            "procedure_sha256": procedures_sha,
            "mode": mode,
            "model": model_name() if state.get("explanation_mode") != "deterministic" else None,
            "action": "employee_decision_required",
            "moves_money": False,
            **public_result(state),
        }
        store.save_investigation(record)
        store.audit(
            p,
            "transaction_investigated",
            record["id"],
            {
                "transaction_id": body.transaction_id,
                "money_status": record["money_status"],
                "causes": [c["code"] for c in record["causes"]],
                "open_questions": [q["code"] for q in record["open_questions"]],
            },
        )
        metrics.inc("mms_investigations_total", outcome=record["money_status"])
        return record

    @app.get("/api/investigations/{investigation_id}")
    def get_investigation(investigation_id: str, p=Depends(principal)):
        record = store.investigation(investigation_id, p["tenant"])
        if not record:
            raise HTTPException(404, "Investigation not found")
        return record

    # ---- Chunking Lab: tune retrieval settings on labeled synthetic questions ----
    lab_embedders, lab_lock = {}, threading.Lock()

    def lab_embedder(name):
        with lab_lock:
            if name not in lab_embedders:
                try:
                    lab_embedders[name] = build_embedder(name)
                except ImportError:
                    raise HTTPException(
                        400, "fastembed not installed; pip install -r requirements-semantic.txt"
                    ) from None
                except ValueError as error:
                    raise HTTPException(400, str(error)) from None
            return lab_embedders[name]

    def lab_policy(p):
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        try:
            return policy_bundle(p["tenant"], today)
        except ValueError:
            raise HTTPException(409, "Applicable policy unavailable") from None

    @app.get("/lab", include_in_schema=False)
    def lab_page():
        return FileResponse(ROOT / "static/lab.html")

    @app.get("/api/lab/chunks")
    def lab_chunks(max_words: int = 60, overlap: int = 15, p=Depends(principal)):
        if not 10 <= max_words <= 200 or not 0 <= overlap < max_words:
            raise HTTPException(422, "Need 10 <= max_words <= 200 and 0 <= overlap < max_words")
        rules, md, digest = lab_policy(p)
        chunks = chunk_policy(md, rules, max_words, overlap)
        return {
            "policy_id": rules["policy_id"],
            "policy_version": rules["version"],
            "policy_sha256": digest,
            "chunks": [
                {
                    "id": c.id,
                    "rule": c.rule,
                    "title": c.title,
                    "position": c.position,
                    "words": len(c.text.split()),
                    "text": c.text,
                }
                for c in chunks
            ],
        }

    @app.post("/api/lab/experiments", status_code=201)
    def lab_run(body: LabExperiment, p=Depends(principal)):
        write_access(p)
        if body.overlap >= body.max_words:
            raise HTTPException(422, "overlap must be smaller than max_words")
        lab_policy(p)
        if p["tenant"] != lab_dataset_tenant():
            raise HTTPException(409, "Labeled questions exist only for the demo tenant")
        settings = RetrievalSettings(
            max_words=body.max_words,
            overlap=body.overlap,
            candidate_k=body.candidate_k,
            rrf_k=body.rrf_k,
            coverage_weight=body.coverage_weight,
        )
        retriever = HybridRetriever(lab_embedder(body.embedder), settings)
        if not capacity.acquire(blocking=False):
            raise HTTPException(429, "Checker busy; try again later")
        try:
            result = run_experiment(retriever, body.split)
        except Exception:
            raise HTTPException(502, "Experiment failed; embedding backend unavailable") from None
        finally:
            capacity.release()
        record = {
            "id": str(uuid.uuid4()),
            "tenant": p["tenant"],
            "actor": p["user"],
            "created_at": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
            "note": body.note,
            "request": body.model_dump(),
            **result,
        }
        store.save_experiment(record)
        store.audit(p, "lab_experiment", record["id"], {"embedder": result["embedder"]})
        return record

    @app.get("/api/lab/experiments")
    def lab_history(p=Depends(principal)):
        return [
            {key: item[key] for key in (
                "id", "created_at", "actor", "note", "split", "embedder", "settings",
                "lexical_baseline", "hybrid", "processing_seconds", "dataset_version",
            )}
            for item in store.experiments(p["tenant"])
        ]

    @app.get("/api/lab/experiments/{experiment_id}")
    def lab_experiment(experiment_id: str, p=Depends(principal)):
        record = store.experiment(experiment_id, p["tenant"])
        if not record:
            raise HTTPException(404, "Experiment not found")
        return record

    return app


def lab_dataset_tenant():
    return load_questions("all")[0]["tenant"]


app = create_app()
