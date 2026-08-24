def test_health(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["checks"] == {"database": "ok", "kafka": "ok"}


def test_correlation_id_is_returned(client) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "test-request"})

    assert response.headers["X-Correlation-ID"] == "test-request"


def test_websocket_health(client) -> None:
    with client.websocket_connect("/ws/health") as websocket:
        assert websocket.receive_json() == {
            "service": "test-service",
            "status": "healthy",
        }
