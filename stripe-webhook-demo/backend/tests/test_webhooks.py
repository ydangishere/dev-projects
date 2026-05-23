import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app

TEST_SECRET = "whsec_test_secret"

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)
    settings.stripe_webhook_secret = TEST_SECRET


def teardown_module():
    Base.metadata.drop_all(bind=engine)


def make_event(event_type: str, event_id: str = "evt_test_123") -> dict:
    return {
        "id": event_id,
        "object": "event",
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_abc",
                "amount_total": 9900,
                "currency": "usd",
                "customer_details": {"email": "user@example.com"},
            }
        },
        "created": int(time.time()),
    }


def generate_test_signature(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def signed_post(event: dict):
    payload = json.dumps(event).encode()
    sig = generate_test_signature(payload, TEST_SECRET)
    return client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": sig})


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_missing_signature():
    response = client.post("/webhooks/stripe", content=b"{}")
    assert response.status_code == 400


def test_webhook_checkout_completed():
    event = make_event("checkout.session.completed")
    response = signed_post(event)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] is True
    assert body["event_type"] == "checkout.session.completed"
    assert body["duplicate"] is False


def test_webhook_idempotency():
    event = make_event("invoice.paid", event_id="evt_dup_001")
    event["data"]["object"] = {
        "id": "in_test",
        "customer": "cus_test",
        "amount_paid": 1500,
        "subscription": "sub_test",
    }

    first = signed_post(event)
    second = signed_post(event)

    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True

    events = client.get("/api/events").json()
    assert len([e for e in events if e["event_id"] == "evt_dup_001"]) == 1
