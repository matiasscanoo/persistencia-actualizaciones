"""Tests de formato de errores y correlation ID (contrato, secciones 4 y 6)."""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_documento_service
from app.core.exceptions import DatabaseError
from app.core.memory_cache import InMemoryCache
from app.core.memory_lock import InMemoryLock
from app.core.memory_repository import InMemoryRepository
from app.core.repository import Repository
from app.main import app
from app.models.documento_pdf import DocumentoPdf
from app.services.documento_service import DocumentoService

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

BODY_VALIDO = {
    "nombre": "contrato.pdf",
    "checksum": CHECKSUM,
    "texto": "Contenido extraído del PDF",
    "tamano_bytes": 245760,
    "paginas": 3,
}


class RepositorioQueFalla(Repository[DocumentoPdf]):
    """Doble que simula MongoDB caído (o un bug no controlado, según el error)."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def add(self, entity: DocumentoPdf) -> DocumentoPdf:
        raise self._error

    async def get_by_id(self, entity_id: str) -> DocumentoPdf | None:
        raise self._error

    async def update(self, entity: DocumentoPdf) -> DocumentoPdf:
        raise self._error

    async def delete(self, entity_id: str) -> DocumentoPdf | None:
        raise self._error


@pytest.fixture(autouse=True)
def _limpiar_overrides():
    yield
    app.dependency_overrides.clear()


def _cliente_con(repository=None, cache=None, lock=None) -> TestClient:
    servicio = DocumentoService(
        repository or InMemoryRepository(),
        cache or InMemoryCache(),
        lock or InMemoryLock(),
    )
    app.dependency_overrides[get_documento_service] = lambda: servicio
    # raise_server_exceptions=False: se quiere el 500 como respuesta, no que
    # TestClient relance la excepción no controlada.
    return TestClient(app, raise_server_exceptions=False)


def test_post_pdf_con_checksum_invalido_devuelve_400_validation_error(cliente_http):
    respuesta = cliente_http.post("/pdf", json={**BODY_VALIDO, "checksum": "abc"})

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"][0]["field"] == "checksum"
    assert error["correlation_id"] == respuesta.headers["X-Correlation-ID"]


def test_post_pdf_con_json_malformado_devuelve_400_con_field_body(cliente_http):
    respuesta = cliente_http.post(
        "/pdf", content=b"esto no es json", headers={"Content-Type": "application/json"}
    )

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"][0]["field"] == "body"


def test_post_pdf_con_campos_extra_devuelve_400(cliente_http):
    respuesta = cliente_http.post("/pdf", json={**BODY_VALIDO, "id": str(uuid4())})

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_pdf_con_id_no_uuid_devuelve_400(cliente_http):
    respuesta = cliente_http.patch("/pdf/no-es-un-uuid", json={"nombre": "x.pdf"})

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"][0]["field"] == "documento_id"


def test_patch_pdf_de_id_inexistente_devuelve_404(cliente_http):
    respuesta = cliente_http.patch(f"/pdf/{uuid4()}", json={"nombre": "x.pdf"})

    assert respuesta.status_code == 404
    error = respuesta.json()["error"]
    assert error["code"] == "RESOURCE_NOT_FOUND"
    assert "id" in error["details"]


def test_post_pdf_con_checksum_duplicado_devuelve_409(cliente_http):
    cliente_http.post("/pdf", json=BODY_VALIDO)

    respuesta = cliente_http.post("/pdf", json={**BODY_VALIDO, "nombre": "otro.pdf"})

    assert respuesta.status_code == 409
    error = respuesta.json()["error"]
    assert error["code"] == "DUPLICATE_CHECKSUM"
    assert error["details"]["checksum"] == CHECKSUM


def test_delete_pdf_repetido_devuelve_404(cliente_http):
    creado = cliente_http.post("/pdf", json=BODY_VALIDO).json()
    cliente_http.delete(f"/pdf/{creado['id']}")

    respuesta = cliente_http.delete(f"/pdf/{creado['id']}")

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_post_pdf_con_mongo_caido_devuelve_503_database_error():
    cliente = _cliente_con(repository=RepositorioQueFalla(DatabaseError()))

    respuesta = cliente.post("/pdf", json=BODY_VALIDO)

    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["code"] == "DATABASE_ERROR"


def test_post_pdf_con_lock_tomado_devuelve_503_lock_timeout():
    lock = InMemoryLock()
    asyncio.run(lock.acquire(f"lock:pdf:checksum:{CHECKSUM}"))
    cliente = _cliente_con(lock=lock)

    respuesta = cliente.post("/pdf", json=BODY_VALIDO)

    assert respuesta.status_code == 503
    error = respuesta.json()["error"]
    assert error["code"] == "DEPENDENCY_UNAVAILABLE"
    assert error["details"]["reason"] == "lock_timeout"


def test_post_pdf_con_error_no_controlado_devuelve_500_sin_filtrar_detalle():
    cliente = _cliente_con(repository=RepositorioQueFalla(RuntimeError("boom")))

    respuesta = cliente.post("/pdf", json=BODY_VALIDO)

    assert respuesta.status_code == 500
    error = respuesta.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "boom" not in respuesta.text
    assert error["correlation_id"] == respuesta.headers["X-Correlation-ID"]


def test_correlation_id_se_respeta_si_viene_en_el_header(cliente_http):
    mio = "abc-123"

    respuesta = cliente_http.get("/health", headers={"X-Correlation-ID": mio})

    assert respuesta.headers["X-Correlation-ID"] == mio


def test_correlation_id_se_genera_si_no_viene(cliente_http):
    respuesta = cliente_http.get("/health")

    assert UUID(respuesta.headers["X-Correlation-ID"])


def test_correlation_id_invalido_se_reemplaza_por_uno_generado(cliente_http):
    invalido = "x" * 200

    respuesta = cliente_http.get("/health", headers={"X-Correlation-ID": invalido})

    assert respuesta.headers["X-Correlation-ID"] != invalido
    assert UUID(respuesta.headers["X-Correlation-ID"])


def test_ruta_inexistente_devuelve_404_en_formato_comun(cliente_http):
    respuesta = cliente_http.get("/no-existe")

    assert respuesta.status_code == 404
    error = respuesta.json()["error"]
    assert error["code"] == "RESOURCE_NOT_FOUND"
    assert error["correlation_id"] == respuesta.headers["X-Correlation-ID"]


def test_metodo_no_permitido_devuelve_405_en_formato_comun(cliente_http):
    # /pdf/{id} existe (PATCH, DELETE), pero no para GET.
    respuesta = cliente_http.get(f"/pdf/{uuid4()}")

    assert respuesta.status_code == 405
    error = respuesta.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["reason"] == "method_not_allowed"
    assert error["correlation_id"] == respuesta.headers["X-Correlation-ID"]


def test_correlation_id_coincide_entre_header_y_error(cliente_http):
    mio = "mi-correlation-id"

    respuesta = cliente_http.post(
        "/pdf",
        json={**BODY_VALIDO, "checksum": "abc"},
        headers={"X-Correlation-ID": mio},
    )

    assert respuesta.headers["X-Correlation-ID"] == mio
    assert respuesta.json()["error"]["correlation_id"] == mio
