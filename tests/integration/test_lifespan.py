"""Test de composición: el lifespan de main.py arma DocumentoService con
adaptadores reales (MongoDB y Redis), sin overrides de dependencia.

Se saltea si no están definidas TEST_MONGO_URI y TEST_REDIS_URL, igual que el
resto de los tests que necesitan servicios reales.
"""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.main import app

TEST_MONGO_URI = os.environ.get("TEST_MONGO_URI")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL")

pytestmark = pytest.mark.skipif(
    not TEST_MONGO_URI or not TEST_REDIS_URL,
    reason="TEST_MONGO_URI o TEST_REDIS_URL no definidas",
)

MONGO_DATABASE = "persistencia_actualizaciones_test"
CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


@pytest.fixture
def entorno_de_integracion(monkeypatch: pytest.MonkeyPatch) -> str:
    """Variables de entorno reales; colección descartable para no ensuciar otras."""
    coleccion = f"lifespan_{uuid4().hex}"
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DATABASE", MONGO_DATABASE)
    monkeypatch.setenv("MONGO_COLLECTION", coleccion)
    monkeypatch.setenv("REDIS_URL", TEST_REDIS_URL)
    monkeypatch.setenv("LOCK_TIMEOUT_SECONDS", "2")
    yield coleccion
    MongoClient(TEST_MONGO_URI)[MONGO_DATABASE][coleccion].drop()


def test_lifespan_arma_documento_service_y_persiste_en_mongo_real(
    entorno_de_integracion: str,
) -> None:
    coleccion = entorno_de_integracion
    body = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 1,
        "paginas": None,
    }

    with TestClient(app) as cliente:
        respuesta = cliente.post("/pdf", json=body)

    assert respuesta.status_code == 201
    guardado = MongoClient(TEST_MONGO_URI)[MONGO_DATABASE][coleccion].find_one(
        {"_id": respuesta.json()["id"]}
    )
    assert guardado is not None
    assert guardado["nombre"] == "contrato.pdf"
    assert guardado["checksum"] == CHECKSUM
