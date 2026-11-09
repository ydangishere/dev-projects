import hashlib
import hmac
import io
import json
import os
import threading
import time
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image
from pypdf import PdfReader
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import evaluate
from .graph import Neo4jGraph, retrieve_module1
from .models import CheckInput, Feedback
from .providers import Gemini, Source, extract_demo
from .rag import policy_bundle, retrieve
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
    if mode not in {"demo", "gemini"}:
        raise ValueError("AI_MODE must be demo or gemini")
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
    if os.getenv("APP_ENV") == "production" and (
        any(len(t) < 32 or t.startswith("demo-") for t in tokens)
    ):
        raise ValueError(
            "Production requires explicit strong tokens; configure SSO upstream"
        )
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
    store = Store(data_dir or os.getenv("DATA_DIR", str(ROOT / "runtime")))
    store.seed(ROOT / "samples/applications.json")
    app = FastAPI(
        title="VietPay MMS AI Document Checker",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )  # /openapi.json remains available for integration.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv(
            "ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
        ).split(","),
    )
    app.add_middleware(Boundary)
    app.state.store, app.state.mode = store, mode
    app.state.graph_backend = graph_backend
    if graph_backend:
        app.add_event_handler("shutdown", graph_backend.close)
    app.state.provider_factory = lambda: Gemini(
        os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    )
    limiter, limit_lock = {}, threading.Lock()
    capacity = threading.BoundedSemaphore(2)
    bearer = HTTPBearer(auto_error=False)

    def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
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
        if name not in {"app.js", "style.css"}:
            raise HTTPException(404)
        return FileResponse(ROOT / "static" / name)

    @app.get("/healthz")
    def health():
        with store.db() as db:
            db.execute("SELECT 1")
        return {
            "status": "ok",
            "mode": mode,
            "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            if mode == "gemini"
            else None,
        }

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
            raise HTTPException(
                422, "Invalid, unsupported, encrypted or oversized document"
            ) from None
        if mode == "demo" and source.mime != "text/plain":
            raise HTTPException(
                422, "Demo reads synthetic TXT only; set AI_MODE=gemini for PDF/images"
            )
        meta = {
            "id": str(uuid.uuid4()),
            "kind": kind,
            "mime": source.mime,
            "pages": source.pages,
            "verification": "pending",
            "verified_version": 0,
            "sha256": hashlib.sha256(data).hexdigest(),
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
        provider = None
        try:
            today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
            try:
                rules, md, digest = policy_bundle(p["tenant"], today)
            except ValueError:
                raise HTTPException(
                    409, "Applicable policy unavailable; manual review required"
                ) from None
            if mode == "gemini":
                try:
                    provider = app.state.provider_factory()
                except Exception:
                    raise HTTPException(
                        503, "Gemini unavailable; check server configuration"
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
                        provider.extract(source) if provider else extract_demo(source)
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
            if suspicious(body.question):
                # Question is never forwarded to the model or used as policy authority.
                events.append(
                    {"stage": "input", "status": "suspicious_question_ignored"}
                )
            sections = retrieve(
                md,
                "required expiry matching verification uncertainty security human review",
                set(rules["rules"].values()),
            )
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
                    explanation_mode = "gemini"
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
                "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
                if provider
                else None,
                "explanation_mode": explanation_mode,
                "summary": "Cần bổ sung hoặc kiểm tra lại."
                if findings
                else "Không phát hiện lỗi trong phạm vi quy tắc demo; nhân viên vẫn quyết định duyệt.",
                "approval": "human_decision_required",
                "policy_id": rules["policy_id"],
                "policy_version": rules["version"],
                "policy_sha256": digest,
                "policy_sections": sections,
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

    return app


app = create_app()
