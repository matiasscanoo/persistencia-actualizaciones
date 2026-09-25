"""Tests unitarios de DocumentoService con dobles en memoria (sin MongoDB ni Redis)."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.core.memory_repository import InMemoryRepository
from app.services.documento_service import DocumentoService

pytestmark = pytest.mark.asyncio

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def datos_documento(**cambios) -> dict:
    datos = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
    }
    return {**datos, **cambios}


@pytest.fixture
def servicio() -> DocumentoService:
    return DocumentoService(InMemoryRepository())


async def test_crear_devuelve_documento_con_los_datos_recibidos(servicio):
    documento = await servicio.crear(**datos_documento())

    assert documento.nombre == "contrato.pdf"
    assert documento.checksum == CHECKSUM
    assert documento.texto == "Contenido extraído del PDF"
    assert documento.tamano_bytes == 245760
    assert documento.paginas == 3


async def test_crear_genera_id_uuid_v4(servicio):
    documento = await servicio.crear(**datos_documento())

    assert UUID(documento.id).version == 4


async def test_crear_genera_ids_distintos_para_cada_documento(servicio):
    primero = await servicio.crear(**datos_documento())
    segundo = await servicio.crear(**datos_documento(checksum="a" * 64))

    assert primero.id != segundo.id


async def test_crear_asigna_fechas_utc_iguales_con_precision_de_milisegundos(servicio):
    antes = datetime.now(timezone.utc)
    documento = await servicio.crear(**datos_documento())
    despues = datetime.now(timezone.utc)

    assert documento.created_at == documento.updated_at
    assert documento.created_at.utcoffset() == timedelta(0)
    assert documento.created_at.microsecond % 1000 == 0
    assert antes - timedelta(milliseconds=1) < documento.created_at <= despues


async def test_crear_sin_paginas_guarda_none(servicio):
    documento = await servicio.crear(**datos_documento(paginas=None))

    assert documento.paginas is None


async def test_crear_acepta_texto_vacio(servicio):
    documento = await servicio.crear(**datos_documento(texto=""))

    assert documento.texto == ""
