"""API tests for Popularity Engine and Human Review endpoints."""

from fastapi.testclient import TestClient

from app.adapters.mocks import MockYouTubeDiscovery
from app.api.main import app
from app.api.v1.discovery import get_youtube_adapter


def _create_source(client: TestClient, key: str) -> str:
    """Helper to discover a source and return its ID."""
    mock_adapter = MockYouTubeDiscovery(
        canned_candidates=[
            {
                "mode": "MOCK",
                "external_id": f"yt_pop_api_{key}",
                "platform": "youtube",
                "title": f"MOCK: Popularity Episode {key}",
                "description": "Episode for testing popularity API endpoints.",
                "channel_id": f"channel_{key}",
                "channel_name": "Test Channel",
                "thumbnail_url": f"https://img.youtube.com/vi/{key}/hqdefault.jpg",
                "views": 350000,
                "likes": 15000,
                "comments": 1200,
                "duration_seconds": 2400,
                "url": f"https://www.youtube.com/watch?v={key}",
                "published_at": "2026-09-10T12:00:00Z",
            }
        ]
    )
    app.dependency_overrides[get_youtube_adapter] = lambda: mock_adapter
    try:
        res = client.post(
            "/api/v1/discovery/youtube",
            json={"topics": [f"PopTest_{key}"], "idempotency_key": key},
        )
        assert res.status_code == 200
        return res.json()["sources"][0]["source_id"]
    finally:
        app.dependency_overrides.pop(get_youtube_adapter, None)


def test_calculate_source_popularity_endpoint(client: TestClient):
    """POST /api/v1/sources/{source_id}/popularity calculates and persists popularity score."""
    source_id = _create_source(client, "pop_calc_01")

    res = client.post(f"/api/v1/sources/{source_id}/popularity", json={})
    assert res.status_code == 200
    data = res.json()

    assert data["source_id"] == source_id
    assert data["algorithm_version"] == "popularity_v1"
    assert data["final_score"] > 0.0
    assert "views_velocity" in data["component_scores"]
    assert "Active components:" in data["rationale"]


def test_get_source_popularity_endpoint(client: TestClient):
    """GET /api/v1/sources/{source_id}/popularity retrieves latest score or 404."""
    source_id = _create_source(client, "pop_get_01")

    # Before calculation: returns 404
    res_before = client.get(f"/api/v1/sources/{source_id}/popularity")
    assert res_before.status_code == 404

    # Calculate popularity
    client.post(f"/api/v1/sources/{source_id}/popularity", json={})

    # After calculation: returns 200
    res_after = client.get(f"/api/v1/sources/{source_id}/popularity")
    assert res_after.status_code == 200
    assert res_after.json()["source_id"] == source_id


def test_human_rights_review_endpoint_authorized(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights/review allows authorized human reviewer to approve."""
    source_id = _create_source(client, "human_rev_01")

    payload = {
        "decision": "APPROVED",
        "evidence_status": "OWNED",
        "reviewer": "sarah_counsel",
        "reviewer_role": "legal_counsel",
        "decision_reason": "Verified primary creator ownership documentation.",
        "evidence_reference": "AFFIDAVIT-DOC-102",
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights/review", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["source_id"] == source_id
    assert data["rights_status"] == "APPROVED"
    assert data["workflow_state"] == "RIGHTS_APPROVED"
    assert data["reviewer"] == "sarah_counsel"
    assert data["evidence_status"] == "OWNED"


def test_human_rights_review_endpoint_rejects_ai_agent(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights/review rejects AI/LLM reviewer with 403."""
    source_id = _create_source(client, "human_rev_ai_01")

    payload = {
        "decision": "APPROVED",
        "evidence_status": "OWNED",
        "reviewer": "auto_evaluator_bot",
        "reviewer_role": "ai_agent",
        "decision_reason": "Automated system determined rights are clear.",
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights/review", json=payload)
    assert res.status_code == 403
    assert "Unauthorized reviewer" in res.json()["error"]["message"]


def test_direct_api_rights_mutation_bypass_rejected(client: TestClient):
    """Attempting to directly submit rights_status: 'APPROVED' to intake API must be rejected."""
    source_id = _create_source(client, "mutation_bypass_01")

    payload = {
        "source_class": "USER_OWNED",
        "license_type": "OWNED",
        "rights_status": "APPROVED",  # Attempting direct status injection
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights", json=payload)
    assert res.status_code == 403
    assert "Direct mutation of rights_status is prohibited" in res.json()["error"]["message"]
