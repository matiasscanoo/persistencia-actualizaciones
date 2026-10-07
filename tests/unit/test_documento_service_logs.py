"""Eventos INFO de cada escritura (contrato 1.2.0), sin datos del documento."""

import logging

import pytest

from app.core.memory_cache import InMemoryCache
from app.core.memory_lock import InMemoryLock
from app.core.memory_repository import InMemoryRepository
from app.services.documento_service import DocumentoService

pytestmark = pytest.mark.asyncio

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
DATOS = {
    "nombre": "contrato-de-juan-perez.pdf",
    "checksum": CHECKSUM,
    "texto": "Contenido privado del PDF",
    "tamano_bytes": 245760,
    "paginas": 3,
}


@pytest.fixture
def servicio() -> DocumentoService:
    return DocumentoService(InMemoryRepository(), InMemoryCache(), InMemoryLock())


def mensajes_info(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]


async def test_crear_registra_el_id_y_el_checksum(servicio, caplog) -> None:
    caplog.set_level(logging.INFO)

    creado = await servicio.crear(**DATOS)

    assert mensajes_info(caplog) == [
        f"documento creado id={creado.id} checksum={CHECKSUM}"
    ]


async def test_actualizar_nombre_registra_el_id(servicio, caplog) -> None:
    creado = await servicio.crear(**DATOS)
    caplog.set_level(logging.INFO)

    await servicio.actualizar_nombre(creado.id, nombre="otro.pdf")

    assert mensajes_info(caplog) == [f"documento modificado id={creado.id}"]


async def test_eliminar_registra_el_id(servicio, caplog) -> None:
    creado = await servicio.crear(**DATOS)
    caplog.set_level(logging.INFO)

    await servicio.eliminar(creado.id)

    assert mensajes_info(caplog) == [f"documento eliminado id={creado.id}"]


async def test_los_logs_no_incluyen_datos_del_documento(servicio, caplog) -> None:
    caplog.set_level(logging.DEBUG)

    creado = await servicio.crear(**DATOS)
    await servicio.actualizar_nombre(creado.id, nombre="nuevo-de-juan-perez.pdf")
    await servicio.eliminar(creado.id)

    todo = "\n".join(r.getMessage() for r in caplog.records)
    assert "juan-perez" not in todo
    assert DATOS["texto"] not in todo
