from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_home_page_is_served() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "AI Meeting Intelligence" in response.text


def test_health_is_local() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["offline"] is True


def test_rejects_unsupported_upload() -> None:
    response = client.post(
        "/api/v1/meetings",
        files={"file": ("meeting.exe", b"not audio", "application/octet-stream")},
    )

    assert response.status_code == 415

