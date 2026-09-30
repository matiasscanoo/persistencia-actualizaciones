"""Test de GET /health: liveness sin depender de MongoDB ni Redis (contrato 3.3)."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_responde_ok_sin_verificar_dependencias() -> None:
    cliente = TestClient(app)

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}
