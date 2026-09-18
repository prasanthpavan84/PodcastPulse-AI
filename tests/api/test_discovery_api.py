"""API tests for YouTube discovery and Job endpoints."""

from fastapi.testclient import TestClient

from app.adapters.mocks import MockYouTubeDiscovery
from app.api.main import app
from app.api.v1.discovery import get_youtube_adapter
from app.core.errors import AppError, ErrorCode


def test_post_discovery_youtube_valid_request(client: TestClient):
    """POST /api/v1/discovery/youtube with valid payload returns 200 and structured discovery summary."""
    mock_adapter = MockYouTubeDiscovery()
    app.dependency_overrides[get_youtube_adapter] = lambda: mock_adapter

    try:
        payload = {
            "topics": ["AI News"],
            "keywords": ["podcast"],
            "min_views": 5000,
            "max_results": 10,
            "idempotency_key": "api_discovery_test_key_01",
        }
        res = client.post("/api/v1/discovery/youtube", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "job_id" in data
        assert data["status"] == "COMPLETED"
        assert data["discovered_count"] >= 1
        assert len(data["sources"]) >= 1
        assert data["sources"][0]["workflow_state"] == "DISCOVERED"
        assert "X-Request-ID" in res.headers
    finally:
        app.dependency_overrides.pop(get_youtube_adapter, None)


def test_post_discovery_validation_errors(client: TestClient):
    """POST /api/v1/discovery/youtube returns 422 when inputs violate validation rules."""
    # 1. Completely empty topics, keywords, and channels
    res1 = client.post("/api/v1/discovery/youtube", json={"topics": []})
    assert res1.status_code == 422

    # 2. Invalid max_results (> 50)
    res2 = client.post("/api/v1/discovery/youtube", json={"topics": ["AI"], "max_results": 100})
    assert res2.status_code == 422

    # 3. Inverted dates (published_after > published_before)
    res3 = client.post(
        "/api/v1/discovery/youtube",
        json={
            "topics": ["Tech"],
            "published_after": "2026-09-10T00:00:00Z",
            "published_before": "2026-09-01T00:00:00Z",
        },
    )
    assert res3.status_code == 422


def test_post_discovery_idempotency_duplicate_request(client: TestClient):
    """POST /api/v1/discovery/youtube with identical idempotency key returns existing job without duplication."""
    mock_adapter = MockYouTubeDiscovery()
    app.dependency_overrides[get_youtube_adapter] = lambda: mock_adapter

    try:
        payload = {
            "topics": ["Science"],
            "idempotency_key": "api_idem_test_duplicate_99",
        }
        res1 = client.post("/api/v1/discovery/youtube", json=payload)
        assert res1.status_code == 200

        res2 = client.post("/api/v1/discovery/youtube", json=payload)
        assert res2.status_code == 200

        assert res1.json()["job_id"] == res2.json()["job_id"]
    finally:
        app.dependency_overrides.pop(get_youtube_adapter, None)


def test_post_discovery_external_quota_exceeded_error_handling(client: TestClient):
    """POST /api/v1/discovery/youtube returns 429 when external quota is exceeded, with no secrets leaked."""
    secret = "AIzaSySecretTestingTokenNotLeaked"

    class QuotaErrorAdapter(MockYouTubeDiscovery):
        def search_candidates(self, *args, **kwargs):
            raise AppError(
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message="YouTube Data API quota exceeded: ***REDACTED***",
                status_code=429,
                retryable=False,
            )

    app.dependency_overrides[get_youtube_adapter] = lambda: QuotaErrorAdapter()

    try:
        payload = {"topics": ["Gaming"], "idempotency_key": "api_quota_error_test"}
        res = client.post("/api/v1/discovery/youtube", json=payload)
        assert res.status_code == 429
        err = res.json()["error"]
        assert err["code"] == "EXTERNAL_SERVICE_ERROR"
        assert secret not in res.text
    finally:
        app.dependency_overrides.pop(get_youtube_adapter, None)


def test_post_discovery_timeout_error_handling(client: TestClient):
    """POST /api/v1/discovery/youtube returns 504 when upstream API times out."""

    class TimeoutAdapter(MockYouTubeDiscovery):
        def search_candidates(self, *args, **kwargs):
            raise AppError(
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message="Connection timeout while contacting YouTube Data API.",
                status_code=504,
                retryable=True,
            )

    app.dependency_overrides[get_youtube_adapter] = lambda: TimeoutAdapter()

    try:
        payload = {"topics": ["TimeoutTopic"], "idempotency_key": "api_timeout_error_test"}
        res = client.post("/api/v1/discovery/youtube", json=payload)
        assert res.status_code == 504
        err = res.json()["error"]
        assert err["retryable"] is True
    finally:
        app.dependency_overrides.pop(get_youtube_adapter, None)


def test_get_job_by_id_endpoint(client: TestClient):
    """GET /api/v1/jobs/{job_id} retrieves job details or returns 404."""
    mock_adapter = MockYouTubeDiscovery()
    app.dependency_overrides[get_youtube_adapter] = lambda: mock_adapter

    try:
        # Run discovery to create a job
        res = client.post(
            "/api/v1/discovery/youtube",
            json={"topics": ["History"], "idempotency_key": "api_get_job_test_01"},
        )
        assert res.status_code == 200
        job_id = res.json()["job_id"]

        # Fetch job by ID
        job_res = client.get(f"/api/v1/jobs/{job_id}")
        assert job_res.status_code == 200
        job_data = job_res.json()
        assert job_data["id"] == job_id
        assert job_data["job_type"] == "DISCOVERY_JOB"
        assert job_data["status"] == "COMPLETED"

        # Fetch non-existent job
        missing_res = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
        assert missing_res.status_code == 404
        assert missing_res.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_youtube_adapter, None)
