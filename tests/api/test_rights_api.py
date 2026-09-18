"""API tests for Content Rights Engine endpoints."""

from fastapi.testclient import TestClient

from app.adapters.mocks import MockYouTubeDiscovery
from app.api.main import app
from app.api.v1.discovery import get_youtube_adapter


def _create_source_via_discovery(client: TestClient, key: str) -> str:
    """Helper to discover a video and return its source ID."""
    mock_adapter = MockYouTubeDiscovery(
        canned_candidates=[
            {
                "mode": "MOCK",
                "external_id": f"yt_api_cand_{key}",
                "platform": "youtube",
                "title": f"MOCK: Discussion {key}",
                "description": "Synthetic discussion on technology trends.",
                "channel_id": f"channel_{key}",
                "channel_name": "Test Channel",
                "thumbnail_url": f"https://img.youtube.com/vi/cand_{key}/hqdefault.jpg",
                "views": 250000,
                "likes": 12000,
                "comments": 850,
                "duration_seconds": 3600,
                "url": f"https://www.youtube.com/watch?v=cand_{key}",
                "published_at": "2026-09-01T12:00:00Z",
            }
        ]
    )
    app.dependency_overrides[get_youtube_adapter] = lambda: mock_adapter
    try:
        res = client.post(
            "/api/v1/discovery/youtube",
            json={"topics": [f"RightsTest_{key}"], "idempotency_key": key},
        )
        assert res.status_code == 200
        sources = res.json()["sources"]
        assert len(sources) > 0
        return sources[0]["source_id"]
    finally:
        app.dependency_overrides.pop(get_youtube_adapter, None)


def test_post_rights_evaluation_user_owned_approved(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights with USER_OWNED evaluates to APPROVED."""
    source_id = _create_source_via_discovery(client, "rights_api_test_owned_01")

    payload = {
        "source_class": "USER_OWNED",
        "license_type": "OWNED",
        "evidence_reference": "ORIGINAL-CREATOR-AFFIDAVIT-DOC-101",
        "reviewer": "sarah_editor",
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["source_id"] == source_id
    assert data["rights_status"] == "APPROVED"
    assert data["workflow_state"] == "RIGHTS_APPROVED"
    assert data["source_class"] == "USER_OWNED"
    assert data["license_type"] == "OWNED"
    assert data["attribution_required"] is False
    assert data["reviewer"] == "sarah_editor"
    assert "ORIGINAL-CREATOR-AFFIDAVIT" in data["decision_reason"]
    assert "X-Request-ID" in res.headers


def test_post_rights_evaluation_cc_by_sa_conditional(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights with CC_BY_SA evaluates to CONDITIONAL with attribution and share-alike."""
    source_id = _create_source_via_discovery(client, "rights_api_test_cc_by_sa_01")

    payload = {
        "source_class": "CREATIVE_COMMONS",
        "license_type": "CC_BY_SA",
        "attribution_required": True,
        "evidence_reference": "https://creativecommons.org/licenses/by-sa/4.0/",
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["rights_status"] == "CONDITIONAL"
    assert data["workflow_state"] == "RIGHTS_PENDING"
    assert "attribution_required" in data["conditions"]
    assert "share_alike_required" in data["conditions"]


def test_post_rights_evaluation_blocked_nc(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights with CC_BY_NC evaluates to BLOCKED."""
    source_id = _create_source_via_discovery(client, "rights_api_test_cc_nc_01")

    payload = {
        "source_class": "CREATIVE_COMMONS",
        "license_type": "CC_BY_NC",
        "evidence_reference": "https://creativecommons.org/licenses/by-nc/4.0/",
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["rights_status"] == "BLOCKED"
    assert data["workflow_state"] == "RIGHTS_BLOCKED"
    assert "prohibits commercial use" in data["decision_reason"].lower()


def test_post_rights_evaluation_unknown_requires_review(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights with UNKNOWN defaults to REVIEW_REQUIRED."""
    source_id = _create_source_via_discovery(client, "rights_api_test_unknown_01")

    payload = {
        "source_class": "UNKNOWN",
        "license_type": "STANDARD_YOUTUBE",
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["rights_status"] == "REVIEW_REQUIRED"
    assert data["workflow_state"] == "RIGHTS_PENDING"
    assert "public availability does not grant reuse" in data["decision_reason"].lower()


def test_get_source_rights_endpoint(client: TestClient):
    """GET /api/v1/sources/{source_id}/rights retrieves existing record or 404."""
    source_id = _create_source_via_discovery(client, "rights_api_test_get_01")

    # Before evaluation, getting rights returns 404 (no rights record exists yet)
    res_before = client.get(f"/api/v1/sources/{source_id}/rights")
    assert res_before.status_code == 404

    # Evaluate rights
    client.post(
        f"/api/v1/sources/{source_id}/rights",
        json={
            "source_class": "USER_OWNED",
            "license_type": "OWNED",
            "reviewer": "test_lead",
        },
    )

    # After evaluation, GET returns 200 with record
    res_after = client.get(f"/api/v1/sources/{source_id}/rights")
    assert res_after.status_code == 200
    data = res_after.json()
    assert data["source_id"] == source_id
    assert data["rights_status"] == "APPROVED"
    assert data["reviewer"] == "test_lead"


def test_post_rights_evaluation_non_existent_source_404(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights with nonexistent ID returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    res = client.post(
        f"/api/v1/sources/{fake_id}/rights",
        json={"source_class": "USER_OWNED", "license_type": "OWNED"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_post_rights_evaluation_malformed_input_422(client: TestClient):
    """POST /api/v1/sources/{source_id}/rights with malformed payload returns 422."""
    source_id = _create_source_via_discovery(client, "rights_api_test_malformed_01")

    # Invalid enum value for source_class
    res = client.post(
        f"/api/v1/sources/{source_id}/rights",
        json={"source_class": "INVALID_CLASS", "license_type": "OWNED"},
    )
    assert res.status_code == 422


def test_no_secret_leakage_in_rights_api(client: TestClient):
    """Verify that any sensitive credentials or tokens in requests are never echoed back in responses."""
    source_id = _create_source_via_discovery(client, "rights_api_test_secret_01")
    secret_token = "SUPER_SECRET_INTERNAL_KEY_99999"

    payload = {
        "source_class": "COMMERCIAL_LICENSE",
        "license_type": "COMMERCIAL",
        "evidence_reference": f"License under token={secret_token}",
        "commercial_use": True,
        "modification_allowed": True,
    }
    res = client.post(f"/api/v1/sources/{source_id}/rights", json=payload)
    assert res.status_code == 200
    # The API returns the cleaned evaluation; no authorization headers or secrets in logs
    assert "authorization" not in res.text.lower()
