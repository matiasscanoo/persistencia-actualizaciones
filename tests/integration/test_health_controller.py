"""GET /health informa MongoDB y Redis (contrato 1.2.0): 503 solo si MongoDB no
responde. Las dependencias se sustituyen con dobles: no hace falta ningún servicio."""

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_salud_service
from app.main import app
from app.services.salud_service import SaludService
from tests.dobles import DependenciaFija


@pytest.fixture
def cliente_con_salud():
    def armar(mongodb: bool, redis: bool) -> TestClient:
        servicio = SaludService(DependenciaFija(mongodb), DependenciaFija(redis))
        app.dependency_overrides[get_salud_service] = lambda: servicio
        return TestClient(app)

    yield armar
    app.dependency_overrides.clear()


def test_health_ok_con_mongodb_y_redis(cliente_con_salud) -> None:
    respuesta = cliente_con_salud(mongodb=True, redis=True).get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "status": "ok",
        "dependencias": {"mongodb": "ok", "redis": "ok"},
    }


def test_health_con_redis_caido_sigue_ok_e_informa(cliente_con_salud) -> None:
    respuesta = cliente_con_salud(mongodb=True, redis=False).get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "status": "ok",
        "dependencias": {"mongodb": "ok", "redis": "caido"},
    }


def test_health_con_mongodb_caido_responde_503(cliente_con_salud) -> None:
    respuesta = cliente_con_salud(mongodb=False, redis=True).get("/health")

    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "status": "error",
        "dependencias": {"mongodb": "caido", "redis": "ok"},
    }
