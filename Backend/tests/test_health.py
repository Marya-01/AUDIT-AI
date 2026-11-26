from fastapi.testclient import TestClient
from app.main import app
# Smoke test; requires PostgreSQL configured and reachable for startup.
def test_health_route():
    with TestClient(app) as client:
        response=client.get("/health")
        assert response.status_code==200
        assert response.json()["status"]=="ok"
