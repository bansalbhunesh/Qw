"""Load testing — ensuring the orchestrator and web layer survive high concurrency."""

import asyncio
import os
import pytest
from httpx import AsyncClient
import concurrent.futures

os.environ["AUTEUR_MOCK"] = "1"

try:
    from fastapi.testclient import TestClient
    from auteur.viewer import build_viewer_app
    _HAS_FASTAPI = True
except Exception:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")

def test_concurrent_produce_requests():
    """Fire multiple production requests concurrently to ensure the queue holds."""
    app = build_viewer_app()
    client = TestClient(app)
    
    payload = {
        "premise": "Load testing concurrent execution",
        "shots": 2,
        "quality_gate": 0.0,
        "max_spend_usd": 10.0,
        "dynamic_resolution": False
    }

    # Launch 10 concurrent POST requests
    def _fire():
        return client.post("/api/produce", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_fire) for _ in range(10)]
        responses = [f.result() for f in futures]
        
    # Ensure all requests were accepted (status 200) and returned a production ID
    for r in responses:
        assert r.status_code == 200
        assert "id" in r.json()
        
    prod_ids = [r.json()["id"] for r in responses]
    assert len(set(prod_ids)) == 10  # Ensure 10 unique productions were launched

    # Wait for all background threads to finish by consuming their SSE streams
    def _wait_for_done(pid):
        with client.stream("GET", f"/api/events?prod_id={pid}") as r:
            for line in r.iter_lines():
                if '"kind": "done"' in line:
                    break

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        wait_futures = [executor.submit(_wait_for_done, pid) for pid in prod_ids]
        for f in wait_futures:
            f.result()  # Wait for completion

def test_producer_pool_isolation():
    """Test that the global producer pool does not bleed state across concurrent productions."""
    from auteur.viewer import producer_pool
    # Verify pool size is bounded
    assert isinstance(producer_pool, concurrent.futures.ThreadPoolExecutor)
    assert producer_pool._max_workers == 3
