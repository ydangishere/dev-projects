"""Synthetic API tests: no device contacts, delivery provider or external LLM."""
import pytest
from fastapi.testclient import TestClient
from app.main import app, INVITES, SYNCED, normalize_phone

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_demo_state(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    SYNCED.clear()
    INVITES.clear()
    yield
    SYNCED.clear()
    INVITES.clear()


def test_readiness_and_linh_rule_mode():
    assert client.get("/health").json()["real_contacts_connected"] is False
    result = client.post("/agent/linh/guide", json={"flow": "invite"}).json()
    assert result["persona"] == "Linh (simulated AI)"
    assert result["mode"] == "rules_demo"
    assert "Picker" in result["advice"]


@pytest.mark.parametrize("permission,consent", [("denied", True), ("full", False), ("not_requested", True)])
def test_sync_requires_permission_and_separate_consent(permission, consent):
    response = client.post("/contacts/sync", json={"permission": permission, "sync_consent": consent,
        "contacts": [{"name": "Demo Person", "phone": "0901234567"}]})
    assert response.status_code == 403


def test_sync_normalizes_deduplicates_and_erases():
    payload = {"permission": "limited", "sync_consent": True, "contacts": [
        {"name": "Demo A", "phone": "0901234567"}, {"name": "Demo A", "phone": "+84901234567"}]}
    response = client.post("/contacts/sync", json=payload, headers={"X-Demo-User": "u1"})
    assert response.status_code == 200
    assert response.json()["synced"] == 1
    assert response.json()["stored"] == "HMAC digests only"
    assert client.get("/contacts/sync/summary", headers={"X-Demo-User": "u1"}).json()["total_unique"] == 1
    assert client.get("/contacts/sync/summary", headers={"X-Demo-User": "u2"}).json()["total_unique"] == 0
    assert client.delete("/contacts/sync", headers={"X-Demo-User": "u1"}).json()["deleted"] == 1


def test_native_picker_invite_does_not_need_sync_permission_or_auto_send():
    payload = {"contact": {"name": "Linh Demo", "phone": "0901234567"},
               "source": "native_picker", "user_selected": True}
    response = client.post("/invitations/draft", json=payload, headers={"X-Demo-User": "u1"})
    assert response.status_code == 200
    draft = response.json()
    assert draft["sent"] is False
    invite_id = draft["id"]
    assert client.post(f"/invitations/{invite_id}/confirm", headers={"X-Demo-User": "u2"}).status_code == 404
    ready = client.post(f"/invitations/{invite_id}/confirm", headers={"X-Demo-User": "u1"}).json()
    assert ready["status"] == "ready_to_share"
    assert ready["sent"] is False
    assert ready["share_url"].startswith("https://example.invalid/")


def test_unselected_contact_cannot_create_invitation():
    response = client.post("/invitations/draft", json={"contact": {"name": "Demo", "phone": "+84901234567"},
        "source": "native_picker", "user_selected": False})
    assert response.status_code == 403


def test_phone_validation():
    assert normalize_phone("0901 234 567") == "+84901234567"
    with pytest.raises(Exception):
        normalize_phone("123")
