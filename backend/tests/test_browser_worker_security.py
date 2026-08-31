import importlib.util
import base64
from pathlib import Path

from fastapi.testclient import TestClient


def load_worker():
    path = Path(__file__).parents[1] / "browser_worker" / "app.py"
    spec = importlib.util.spec_from_file_location("jarvis_browser_worker", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_worker_requires_internal_bearer_and_rejects_profile_override(monkeypatch):
    worker = load_worker()
    token = base64.b64encode(b"x" * 32).decode()
    monkeypatch.setattr(worker, "BROWSER_WORKER_TOKEN", token)
    with TestClient(worker.app) as client:
        assert client.get("/health").status_code == 401
        assert client.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/health", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        response = client.post(
            "/sessions/connect", headers={"Authorization": f"Bearer {token}"},
            json={"site": "amazon", "profile_path": "C:/untrusted"},
        )
        assert response.status_code == 422
