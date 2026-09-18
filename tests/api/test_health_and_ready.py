"""API tests for health, readiness, and middleware behavior."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_endpoint_is_live_without_db(client: TestClient):
    """GET /api/v1/health must return 200 ok and application version."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_ready_endpoint_reports_connected_when_db_available(client: TestClient):
    """GET /api/v1/ready returns ready and database connected when MySQL is active."""
    res = client.get("/api/v1/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_ready_endpoint_reports_503_when_db_down(client: TestClient):
    """GET /api/v1/ready returns 503 not_ready when MySQL connection fails."""
    with patch("app.api.v1.health.check_database_connection", return_value=False):
        res = client.get("/api/v1/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "disconnected"


def test_correlation_id_middleware_assigns_header(client: TestClient):
    """Responses must include X-Request-ID and propagate incoming values."""
    # When no header sent, a UUID is generated
    res = client.get("/api/v1/health")
    assert "X-Request-ID" in res.headers
    assert len(res.headers["X-Request-ID"]) > 0

    # When header is sent, it is preserved
    custom_id = "test-req-id-12345"
    res2 = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert res2.headers.get("X-Request-ID") == custom_id
