from fastapi.testclient import TestClient
import mock_service


def test_mock_success_response_schema(monkeypatch):
    monkeypatch.setattr(mock_service.random, "random", lambda: 0.99)
    monkeypatch.setattr(mock_service.random, "lognormvariate", lambda _mu, _sigma: 1.0)
    client = TestClient(mock_service.app)
    response = client.post("/pipeline/process", json={"event_id": "x", "audio_ref": "synthetic"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "transcript": "synthetic transcript", "response_audio_ref": "synthetic", "latency_ms": 1.0}


def test_mock_failure_response_schema(monkeypatch):
    monkeypatch.setattr(mock_service.random, "random", lambda: 0.01)
    client = TestClient(mock_service.app)
    response = client.post("/pipeline/process", json={"event_id": "x", "audio_ref": "synthetic"})
    assert response.status_code == 503
    assert response.json() == {"status": "error", "reason": "downstream_timeout"}
