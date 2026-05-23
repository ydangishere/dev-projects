from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_assessment():
    payload = {
        "title": "Device Safety Check",
        "subject_name": "Acme MedTech",
        "score": 88.5,
        "status": "submitted",
        "notes": "Initial audit run",
    }
    create_response = client.post("/api/assessments", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == payload["title"]

    list_response = client.get("/api/assessments")
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1


def test_billing_status_updates_after_create():
    client.post(
        "/api/assessments",
        json={
            "title": "Compliance Review",
            "subject_name": "Beta Clinic",
            "score": 92,
            "status": "reviewed",
        },
    )
    billing_response = client.get("/api/billing/status")
    assert billing_response.status_code == 200
    billing = billing_response.json()
    assert billing["assessments_used"] >= 1
    assert billing["remaining"] <= billing["assessments_limit"]
