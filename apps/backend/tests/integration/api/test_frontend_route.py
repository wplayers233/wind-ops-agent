from fastapi.testclient import TestClient

from app.main import app

MAIN_PY_MARKER = "ROOT_DIR = Path(__file__).resolve().parents[3]"


def test_frontend_route_rejects_path_traversal():
    client = TestClient(app)
    traversals = [
        "/..%2f..%2fbackend%2fapp%2fmain.py",
        "/%2e%2e/%2e%2e/backend/app/main.py",
        "/assets/..%2f..%2f..%2fapp%2fmain.py",
    ]
    for target in traversals:
        response = client.get(target, follow_redirects=False)
        assert MAIN_PY_MARKER not in response.text, f"traversal leaked source for {target}"


def test_frontend_route_serves_dist_or_404():
    client = TestClient(app)
    response = client.get("/some-unknown-spa-route")
    assert response.status_code in {200, 404}
    if response.status_code == 200:
        assert "assets/" in response.text or "<!doctype html>" in response.text.lower()
