import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "checker.sqlite3"
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, body TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, application_id TEXT NOT NULL, kind TEXT NOT NULL,
                meta TEXT NOT NULL, data BLOB NOT NULL, UNIQUE(application_id,kind));
            CREATE TABLE IF NOT EXISTS checks (
                id TEXT PRIMARY KEY, application_id TEXT NOT NULL, tenant TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence (
                check_id TEXT NOT NULL, document_id TEXT NOT NULL, meta TEXT NOT NULL, data BLOB NOT NULL,
                PRIMARY KEY(check_id,document_id));
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, tenant TEXT NOT NULL,
                action TEXT NOT NULL, object_id TEXT NOT NULL, details TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def audit(self, principal, action, object_id, details=None):
        with self.db() as db:
            db.execute(
                "INSERT INTO audit(at,actor,tenant,action,object_id,details) VALUES(?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    principal["user"],
                    principal["tenant"],
                    action,
                    object_id,
                    json.dumps(details or {}, ensure_ascii=False),
                ),
            )

    def seed(self, sample_path):
        for sample in json.loads(Path(sample_path).read_text(encoding="utf-8")):
            with self.db() as db:
                cursor = db.execute(
                    "INSERT OR IGNORE INTO applications VALUES(?,?,?,1)",
                    (sample["id"], sample["tenant"], json.dumps(sample["application"])),
                )
                if not cursor.rowcount:
                    continue
                for item in sample["documents"]:
                    meta = {k: v for k, v in item.items() if k != "text"}
                    meta["mime"] = "text/plain"
                    meta["pages"] = 1
                    db.execute(
                        "INSERT INTO documents VALUES(?,?,?,?,?)",
                        (
                            item["id"],
                            sample["id"],
                            item["kind"],
                            json.dumps(meta),
                            item["text"].encode(),
                        ),
                    )

    def application(self, app_id, tenant):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM applications WHERE id=? AND tenant=?", (app_id, tenant)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "tenant": row["tenant"],
                "revision": row["revision"],
                **json.loads(row["body"]),
            }

    def applications(self, tenant):
        with self.db() as db:
            rows = db.execute(
                "SELECT id FROM applications WHERE tenant=? ORDER BY id", (tenant,)
            ).fetchall()
        return [self.application(r["id"], tenant) for r in rows]

    def documents(self, app_id):
        with self.db() as db:
            rows = db.execute(
                "SELECT meta,data FROM documents WHERE application_id=? ORDER BY kind",
                (app_id,),
            ).fetchall()
        return [(json.loads(r["meta"]), bytes(r["data"])) for r in rows]

    def put_document(self, app_id, meta, data):
        with self.db() as db:
            old = db.execute(
                "SELECT meta FROM documents WHERE application_id=? AND kind=?",
                (app_id, meta["kind"]),
            ).fetchone()
            meta["version"] = json.loads(old["meta"])["version"] + 1 if old else 1
            if old:
                db.execute(
                    "DELETE FROM documents WHERE application_id=? AND kind=?",
                    (app_id, meta["kind"]),
                )
            db.execute(
                "INSERT INTO documents VALUES(?,?,?,?,?)",
                (meta["id"], app_id, meta["kind"], json.dumps(meta), data),
            )
            db.execute(
                "UPDATE applications SET revision=revision+1 WHERE id=?", (app_id,)
            )
        return meta

    def save_check(self, result, documents):
        with self.db() as db:
            db.execute(
                "INSERT INTO checks VALUES(?,?,?,?)",
                (
                    result["id"],
                    result["application_id"],
                    result["tenant"],
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            for meta, data in documents:
                db.execute(
                    "INSERT INTO evidence VALUES(?,?,?,?)",
                    (result["id"], meta["id"], json.dumps(meta), data),
                )

    def check(self, check_id, tenant):
        with self.db() as db:
            row = db.execute(
                "SELECT body FROM checks WHERE id=? AND tenant=?", (check_id, tenant)
            ).fetchone()
        return json.loads(row["body"]) if row else None

    def evidence(self, check_id, doc_id):
        with self.db() as db:
            row = db.execute(
                "SELECT meta,data FROM evidence WHERE check_id=? AND document_id=?",
                (check_id, doc_id),
            ).fetchone()
        return (json.loads(row["meta"]), bytes(row["data"])) if row else None
