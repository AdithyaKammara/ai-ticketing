from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_health_returns_ok(offline_client: TestClient) -> None:
    response = offline_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_id_is_echoed(offline_client: TestClient) -> None:
    response = offline_client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"


def test_request_id_is_generated_when_missing(offline_client: TestClient) -> None:
    response = offline_client.get("/api/v1/health")

    assert len(response.headers["X-Request-ID"]) == 32


def test_ready_returns_503_when_dependencies_are_down(offline_client: TestClient) -> None:
    response = offline_client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": False, "redis": False},
    }


async def test_ready_returns_ok_when_dependencies_are_up(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": True, "redis": True}}


def test_unknown_route_uses_error_shape(offline_client: TestClient) -> None:
    response = offline_client.get("/api/v1/nope", headers={"X-Request-ID": "req-1"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not Found", "details": {}},
        "request_id": "req-1",
    }
