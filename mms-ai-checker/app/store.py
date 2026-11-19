import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .crypto import Cipher


class Store:
    def __init__(self, directory, cipher: Cipher | None = None):
        # Sensitive columns (application body, document bytes, check body, evidence
        # bytes) are sealed with AES-GCM when a key is configured. See app/crypto.py.
        self.cipher = cipher or Cipher()
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
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, created_at TEXT NOT NULL,
                actor TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, created_at TEXT NOT NULL,
                actor TEXT NOT NULL, transaction_id TEXT NOT NULL, body TEXT NOT NULL);
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
                    (
                        sample["id"],
                        sample["tenant"],
                        self.cipher.seal_text(
                            json.dumps(sample["application"]),
                            f"applications.body:{sample['id']}",
                        ),
                    ),
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
                            self.cipher.seal(
                                item["text"].encode(), f"documents.data:{item['id']}"
                            ),
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
                **json.loads(
                    self.cipher.open_text(row["body"], f"applications.body:{row['id']}")
                ),
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
                "SELECT id,meta,data FROM documents WHERE application_id=? ORDER BY kind",
                (app_id,),
            ).fetchall()
        return [
            (
                json.loads(r["meta"]),
                self.cipher.open(bytes(r["data"]), f"documents.data:{r['id']}"),
            )
            for r in rows
        ]

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
                (
                    meta["id"],
                    app_id,
                    meta["kind"],
                    json.dumps(meta),
                    self.cipher.seal(data, f"documents.data:{meta['id']}"),
                ),
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
                    self.cipher.seal_text(
                        json.dumps(result, ensure_ascii=False), f"checks.body:{result['id']}"
                    ),
                ),
            )
            for meta, data in documents:
                db.execute(
                    "INSERT INTO evidence VALUES(?,?,?,?)",
                    (
                        result["id"],
                        meta["id"],
                        json.dumps(meta),
                        self.cipher.seal(data, f"evidence.data:{result['id']}/{meta['id']}"),
                    ),
                )

    def check(self, check_id, tenant):
        with self.db() as db:
            row = db.execute(
                "SELECT body FROM checks WHERE id=? AND tenant=?", (check_id, tenant)
            ).fetchone()
        if not row:
            return None
        return json.loads(self.cipher.open_text(row["body"], f"checks.body:{check_id}"))

    def save_experiment(self, record):
        with self.db() as db:
            db.execute(
                "INSERT INTO experiments VALUES(?,?,?,?,?)",
                (
                    record["id"],
                    record["tenant"],
                    record["created_at"],
                    record["actor"],
                    json.dumps(record, ensure_ascii=False),
                ),
            )

    def experiments(self, tenant, limit=50):
        with self.db() as db:
            rows = db.execute(
                "SELECT body FROM experiments WHERE tenant=? ORDER BY created_at DESC LIMIT ?",
                (tenant, limit),
            ).fetchall()
        return [json.loads(r["body"]) for r in rows]

    def experiment(self, experiment_id, tenant):
        with self.db() as db:
            row = db.execute(
                "SELECT body FROM experiments WHERE id=? AND tenant=?",
                (experiment_id, tenant),
            ).fetchone()
        return json.loads(row["body"]) if row else None

    def save_investigation(self, record):
        with self.db() as db:
            db.execute(
                "INSERT INTO investigations VALUES(?,?,?,?,?,?)",
                (
                    record["id"],
                    record["tenant"],
                    record["created_at"],
                    record["actor"],
                    record["transaction_id"],
                    self.cipher.seal_text(
                        json.dumps(record, ensure_ascii=False), f"investigations.body:{record['id']}"
                    ),
                ),
            )

    def investigation(self, investigation_id, tenant):
        with self.db() as db:
            row = db.execute(
                "SELECT body FROM investigations WHERE id=? AND tenant=?",
                (investigation_id, tenant),
            ).fetchone()
        if not row:
            return None
        return json.loads(
            self.cipher.open_text(row["body"], f"investigations.body:{investigation_id}")
        )

    def evidence(self, check_id, doc_id):
        with self.db() as db:
            row = db.execute(
                "SELECT meta,data FROM evidence WHERE check_id=? AND document_id=?",
                (check_id, doc_id),
            ).fetchone()
        if not row:
            return None
        data = self.cipher.open(bytes(row["data"]), f"evidence.data:{check_id}/{doc_id}")
        return json.loads(row["meta"]), data

    def rotate(self):
        """Re-seal every sensitive value with the current key (or plaintext if none)."""
        columns = [
            ("applications", "body", "id", lambda r: f"applications.body:{r['id']}", True),
            ("documents", "data", "id", lambda r: f"documents.data:{r['id']}", False),
            ("checks", "body", "id", lambda r: f"checks.body:{r['id']}", True),
            ("investigations", "body", "id", lambda r: f"investigations.body:{r['id']}", True),
        ]
        changed = 0
        with self.db() as db:
            for table, column, key, aad, text in columns:
                for row in db.execute(f"SELECT {key},{column} FROM {table}").fetchall():
                    value = row[column] if text else bytes(row[column])
                    if self.cipher.is_current(value):
                        continue
                    if text:
                        new = self.cipher.seal_text(self.cipher.open_text(value, aad(row)), aad(row))
                    else:
                        new = self.cipher.seal(self.cipher.open(value, aad(row)), aad(row))
                    db.execute(f"UPDATE {table} SET {column}=? WHERE {key}=?", (new, row[key]))
                    changed += 1
            for row in db.execute("SELECT check_id,document_id,data FROM evidence").fetchall():
                value, aad = bytes(row["data"]), f"evidence.data:{row['check_id']}/{row['document_id']}"
                if self.cipher.is_current(value):
                    continue
                db.execute(
                    "UPDATE evidence SET data=? WHERE check_id=? AND document_id=?",
                    (self.cipher.seal(self.cipher.open(value, aad), aad), row["check_id"], row["document_id"]),
                )
                changed += 1
        return changed
