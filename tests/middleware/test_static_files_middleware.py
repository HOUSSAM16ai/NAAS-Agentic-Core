import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pathlib import Path
from starlette.requests import Request
import os

from app.middleware.static_files_middleware import (
    StaticFilesConfig,
    setup_static_files_middleware,
    _should_enable_static_files,
    _is_api_path,
)


@pytest.fixture
def dummy_static_dir(tmp_path: Path) -> str:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>Index Middleware</html>")
    (static_dir / "css").mkdir()
    (static_dir / "css/style.css").write_text("body {}")
    (static_dir / "missing.txt").write_text("missing")
    return str(static_dir)


def test_should_enable_static_files_disabled():
    config = StaticFilesConfig(enabled=False)
    assert _should_enable_static_files(config) is False


def test_should_enable_static_files_missing_dir(tmp_path):
    config = StaticFilesConfig(enabled=True, static_dir=str(tmp_path / "nonexistent"))
    assert _should_enable_static_files(config) is False


def test_should_enable_static_files_enabled(dummy_static_dir):
    config = StaticFilesConfig(enabled=True, static_dir=dummy_static_dir)
    assert _should_enable_static_files(config) is True


def test_is_api_path():
    assert _is_api_path("api") is True
    assert _is_api_path("/api/v1") is True
    assert _is_api_path("v1/api") is True
    assert _is_api_path("/assets") is False


def test_middleware_serve_index_at_root(dummy_static_dir):
    app = FastAPI()
    config = StaticFilesConfig(static_dir=dummy_static_dir)
    setup_static_files_middleware(app, config)

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "<html>Index Middleware</html>"


def test_middleware_serve_static_asset(dummy_static_dir, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    app = FastAPI()
    config = StaticFilesConfig(static_dir=dummy_static_dir)
    setup_static_files_middleware(app, config)

    client = TestClient(app)
    response = client.get("/css/style.css")
    assert response.status_code == 200
    assert response.text == "body {}"


def test_middleware_spa_fallback_for_routes(dummy_static_dir, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    app = FastAPI()
    config = StaticFilesConfig(static_dir=dummy_static_dir)
    setup_static_files_middleware(app, config)

    client = TestClient(app)
    response = client.get("/dashboard/user")
    assert response.status_code == 200
    assert response.text == "<html>Index Middleware</html>"


def test_middleware_api_404_no_fallback(dummy_static_dir, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    app = FastAPI()
    config = StaticFilesConfig(static_dir=dummy_static_dir)
    setup_static_files_middleware(app, config)

    client = TestClient(app)
    response = client.get("/api/v1/missing")
    assert response.status_code == 404
    assert response.text != "<html>Index Middleware</html>"


def test_middleware_nested_api_404_no_fallback(dummy_static_dir, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    app = FastAPI()
    config = StaticFilesConfig(static_dir=dummy_static_dir)
    setup_static_files_middleware(app, config)

    client = TestClient(app)
    response = client.get("/admin/api/chat/ws")
    assert response.status_code == 404
    assert response.text != "<html>Index Middleware</html>"


def test_middleware_directory_traversal_protection(dummy_static_dir, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    app = FastAPI()
    config = StaticFilesConfig(static_dir=dummy_static_dir)
    setup_static_files_middleware(app, config)

    client = TestClient(app)
    response = client.get("/../etc/passwd")

    # Path traversal should either fallback to SPA index.html or return 404 depending on client logic
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert response.text == "<html>Index Middleware</html>"


def test_middleware_spa_fallback_rejects_disallowed_method(dummy_static_dir, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    app = FastAPI()
    config = StaticFilesConfig(static_dir=dummy_static_dir)
    setup_static_files_middleware(app, config)

    client = TestClient(app)

    # Attempt POST on existing file
    response = client.post("/missing.txt")
    assert response.status_code == 405

    # Attempt POST on missing SPA route
    response = client.post("/some/spa/route")
    assert response.status_code == 404
