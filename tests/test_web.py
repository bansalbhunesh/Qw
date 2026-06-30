"""Web layer tests — viewer + deploy API endpoints (mock mode, no spend)."""

import os
import warnings

os.environ["AUTEUR_MOCK"] = "1"
warnings.filterwarnings("ignore")

import pytest

try:
    from fastapi.testclient import TestClient
    _HAS_FASTAPI = True
except Exception:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")


def _viewer():
    from auteur.viewer import build_viewer_app
    return TestClient(build_viewer_app())


def _deploy():
    from deploy.alibaba_cloud import build_app
    return TestClient(build_app())


def test_viewer_index_serves_html():
    r = _viewer().get("/")
    assert r.status_code == 200
    assert "Auteur" in r.text


def test_viewer_gallery_page():
    r = _viewer().get("/gallery")
    assert r.status_code == 200
    assert "Gallery" in r.text


def test_viewer_metrics_endpoint():
    r = _viewer().get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    for key in ("productions", "avg_score", "total_tokens", "avg_tokens_per_film"):
        assert key in body


def test_viewer_gallery_api_returns_list():
    r = _viewer().get("/api/gallery")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_viewer_openapi_schema_builds():
    """OpenAPI generation must succeed — proves request models are module-level."""
    r = _viewer().get("/openapi.json")
    assert r.status_code == 200
    assert r.json().get("paths")


def test_deploy_healthz():
    r = _deploy().get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_deploy_metrics_and_gallery():
    c = _deploy()
    assert c.get("/metrics").status_code == 200
    assert isinstance(c.get("/gallery").json(), list)


def test_deploy_openapi_schema_builds():
    r = _deploy().get("/openapi.json")
    assert r.status_code == 200
    assert r.json().get("paths")


def test_web_endpoints_critique(tmp_path):
    # Setup dummy video
    from auteur.media import make_placeholder_clip
    dummy_video = tmp_path / "dummy_critique.mp4"
    make_placeholder_clip(dummy_video, 0, seconds=2.0)

    # 1. Test deploy API critique
    deploy_client = _deploy()
    r = deploy_client.post("/critique", json={"video_url": str(dummy_video), "prompt": "A person in a room"})
    assert r.status_code == 200
    res = r.json()
    assert "overall" in res
    assert res["overall"] > 0

    # 2. Test viewer API critique
    viewer_client = _viewer()
    r = viewer_client.post("/api/critique", json={"video_url": str(dummy_video), "prompt": "A person in a room"})
    assert r.status_code == 200
    res = r.json()
    assert "overall" in res
    assert res["overall"] > 0
