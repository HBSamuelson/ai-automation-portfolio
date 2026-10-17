from fastapi.testclient import TestClient

from support_agent.webapp import create_app


def client():
    return TestClient(create_app("mock"))


def test_home_and_health():
    api = client()
    page = api.get("/")
    assert page.status_code == 200
    assert "Northline" in page.text
    assert "Fictional shop" in page.text
    health = api.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert body["as_of"] == "2026-10-07"
    assert body["store"] == "Northline Supply"


def test_chat_resolves_and_escalates():
    api = client()
    faq = api.post("/api/chat", json={"message": "How long does standard shipping take?"})
    assert faq.status_code == 200
    assert "4-7 business days" in faq.json()["reply"]
    assert faq.json()["tickets"] == []

    human = api.post("/api/chat", json={"message": "Let me talk to a real person."})
    assert human.status_code == 200
    ticket = human.json()["tickets"][0]
    assert ticket["reason_code"] == "customer_requested_human"
    assert "TCK-" in human.json()["reply"]


def test_sessions_are_isolated_and_multi_turn():
    api = client()
    first = api.post("/api/chat", json={"message": "Can you check my order?"})
    session_id = first.json()["session_id"]
    second = api.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "It's ORD-1042 for ava.chen@northline.example",
        },
    )
    assert "NL-TRK-1042" in second.json()["reply"]

    other = api.post("/api/chat", json={"message": "Let me talk to a real person."})
    assert other.json()["session_id"] != session_id
    assert other.json()["tickets"][0]["id"] == "TCK-1001"
    assert second.json()["tickets"] == []


def test_blank_and_unknown_session():
    api = client()
    blank = api.post("/api/chat", json={"message": "   "})
    assert blank.status_code == 400
    missing = api.post("/api/chat", json={"session_id": "missing", "message": "hello"})
    assert missing.status_code == 404
