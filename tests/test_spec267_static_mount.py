"""SPEC-267 — a API só serve web/dist; sem build não há UI de fallback (o CI roda pytest antes do build)."""

import os

from fastapi.testclient import TestClient

import api


def _has_mount() -> bool:
    return any(getattr(r, "name", "") == "frontend" for r in api.app.routes)


def test_mount_follows_web_dist_presence():
    assert _has_mount() == os.path.isdir(os.path.join(api._ROOT, "web", "dist"))


def test_health_and_root_without_dist():
    client = TestClient(api.app)
    assert client.get("/health").status_code == 200
    if _has_mount():
        assert client.get("/").status_code == 200
    else:
        assert client.get("/").status_code == 404
        assert not os.path.isdir(os.path.join(api._ROOT, "frontend"))
