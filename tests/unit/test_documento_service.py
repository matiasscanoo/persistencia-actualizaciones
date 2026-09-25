"""Tests unitarios de DocumentoService con dobles en memoria (sin MongoDB ni Redis)."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.core.cache import Cache
from app.core.exceptions import (
    CacheUnavailableError,
    DuplicateChecksumError,
    ResourceNotFoundError,
)
from app.core.memory_cache import InMemoryCache
from app.core.memory_repository import InMemoryRepository
from app.models.documento_pdf import DocumentoPdf
from app.services.documento_service import DocumentoService

pytestmark = pytest.mark.asyncio

FECHA_ANTERIOR = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
LISTADOS = {"pdf:list:pagina=1", "pdf:list:pagina=2"}
CLAVES_DE_OTRO_DOCUMENTO = {"pdf:id:otro-documento", "pdf:checksum:" + "b" * 64}


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
def repositorio() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def cache() -> InMemoryCache:
    return InMemoryCache()


@pytest.fixture
def servicio(repositorio, cache) -> DocumentoService:
    return DocumentoService(repositorio, cache)


class CacheNoDisponible(Cache):
    """Doble de una caché caída: toda invalidación falla como Redis sin conexión."""

    async def invalidate(self, keys: list[str]) -> None:
        raise CacheUnavailableError("Redis no responde")


@pytest.fixture
def servicio_con_cache_caida(repositorio) -> DocumentoService:
    return DocumentoService(repositorio, CacheNoDisponible())


def claves_de(documento: DocumentoPdf) -> set[str]:
    """Claves que persistencia-consultas cachea para un documento."""
    return {f"pdf:id:{documento.id}", f"pdf:checksum:{documento.checksum}"}


def hay_warning_con(caplog, texto: str) -> bool:
    return any(
        r.levelno == logging.WARNING and texto in r.getMessage() for r in caplog.records
    )


async def guardar_documento_anterior(repositorio) -> DocumentoPdf:
    """Guarda un documento con fechas viejas, para comparar sin depender del reloj."""
    documento = DocumentoPdf(
        **datos_documento(), created_at=FECHA_ANTERIOR, updated_at=FECHA_ANTERIOR
    )
    return await repositorio.add(documento)


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


async def test_crear_con_checksum_duplicado_lanza_duplicate_checksum_error(servicio):
    await servicio.crear(**datos_documento())

    with pytest.raises(DuplicateChecksumError) as error:
        await servicio.crear(**datos_documento(nombre="otro-nombre.pdf"))

    assert error.value.checksum == CHECKSUM
    assert error.value.error_code == "DUPLICATE_CHECKSUM"


async def test_actualizar_nombre_devuelve_el_documento_con_el_nombre_nuevo(
    servicio, repositorio
):
    guardado = await guardar_documento_anterior(repositorio)

    actualizado = await servicio.actualizar_nombre(guardado.id, nombre="nuevo.pdf")

    assert actualizado.id == guardado.id
    assert actualizado.nombre == "nuevo.pdf"


async def test_actualizar_nombre_renueva_updated_at_y_conserva_el_resto(
    servicio, repositorio
):
    guardado = await guardar_documento_anterior(repositorio)

    actualizado = await servicio.actualizar_nombre(guardado.id, nombre="nuevo.pdf")

    assert actualizado.updated_at > FECHA_ANTERIOR
    assert actualizado.created_at == FECHA_ANTERIOR
    assert actualizado.checksum == CHECKSUM
    assert actualizado.texto == "Contenido extraído del PDF"
    assert actualizado.tamano_bytes == 245760
    assert actualizado.paginas == 3


async def test_actualizar_nombre_persiste_el_cambio(servicio, repositorio):
    guardado = await guardar_documento_anterior(repositorio)

    await servicio.actualizar_nombre(guardado.id, nombre="nuevo.pdf")

    persistido = await repositorio.get_by_id(guardado.id)
    assert persistido.nombre == "nuevo.pdf"
    assert persistido.updated_at > FECHA_ANTERIOR


async def test_actualizar_nombre_de_id_inexistente_lanza_resource_not_found(servicio):
    id_inexistente = str(uuid4())

    with pytest.raises(ResourceNotFoundError) as error:
        await servicio.actualizar_nombre(id_inexistente, nombre="nuevo.pdf")

    assert error.value.id == id_inexistente
    assert error.value.error_code == "RESOURCE_NOT_FOUND"


async def test_eliminar_borra_el_documento(servicio, repositorio):
    guardado = await guardar_documento_anterior(repositorio)

    await servicio.eliminar(guardado.id)

    assert await repositorio.get_by_id(guardado.id) is None


async def test_eliminar_libera_el_checksum_para_un_documento_nuevo(
    servicio, repositorio
):
    guardado = await guardar_documento_anterior(repositorio)

    await servicio.eliminar(guardado.id)
    nuevo = await servicio.crear(**datos_documento())

    assert nuevo.checksum == CHECKSUM


async def test_eliminar_id_inexistente_lanza_resource_not_found(servicio):
    id_inexistente = str(uuid4())

    with pytest.raises(ResourceNotFoundError) as error:
        await servicio.eliminar(id_inexistente)

    assert error.value.id == id_inexistente


async def test_eliminar_dos_veces_lanza_resource_not_found(servicio, repositorio):
    guardado = await guardar_documento_anterior(repositorio)
    await servicio.eliminar(guardado.id)

    with pytest.raises(ResourceNotFoundError):
        await servicio.eliminar(guardado.id)


async def test_crear_invalida_checksum_y_listados(servicio, cache):
    cache.claves.update(
        {f"pdf:checksum:{CHECKSUM}"} | LISTADOS | CLAVES_DE_OTRO_DOCUMENTO
    )

    await servicio.crear(**datos_documento())

    assert cache.claves == CLAVES_DE_OTRO_DOCUMENTO


async def test_actualizar_nombre_invalida_id_checksum_y_listados(
    servicio, repositorio, cache
):
    guardado = await guardar_documento_anterior(repositorio)
    cache.claves.update(claves_de(guardado) | LISTADOS | CLAVES_DE_OTRO_DOCUMENTO)

    await servicio.actualizar_nombre(guardado.id, nombre="nuevo.pdf")

    assert cache.claves == CLAVES_DE_OTRO_DOCUMENTO


async def test_eliminar_invalida_id_checksum_y_listados(servicio, repositorio, cache):
    guardado = await guardar_documento_anterior(repositorio)
    cache.claves.update(claves_de(guardado) | LISTADOS | CLAVES_DE_OTRO_DOCUMENTO)

    await servicio.eliminar(guardado.id)

    assert cache.claves == CLAVES_DE_OTRO_DOCUMENTO


async def test_crear_duplicado_no_invalida_la_cache(servicio, repositorio, cache):
    guardado = await guardar_documento_anterior(repositorio)
    cache.claves.update(claves_de(guardado) | LISTADOS)

    with pytest.raises(DuplicateChecksumError):
        await servicio.crear(**datos_documento())

    assert cache.claves == claves_de(guardado) | LISTADOS


async def test_actualizar_nombre_inexistente_no_invalida_la_cache(servicio, cache):
    cache.claves.update(LISTADOS)

    with pytest.raises(ResourceNotFoundError):
        await servicio.actualizar_nombre(str(uuid4()), nombre="nuevo.pdf")

    assert cache.claves == LISTADOS


async def test_eliminar_inexistente_no_invalida_la_cache(servicio, cache):
    cache.claves.update(LISTADOS)

    with pytest.raises(ResourceNotFoundError):
        await servicio.eliminar(str(uuid4()))

    assert cache.claves == LISTADOS


async def test_crear_con_cache_caida_persiste_y_registra_warning(
    servicio_con_cache_caida, repositorio, caplog
):
    documento = await servicio_con_cache_caida.crear(**datos_documento())

    assert await repositorio.get_by_id(documento.id) is not None
    assert hay_warning_con(caplog, f"pdf:checksum:{CHECKSUM}")


async def test_actualizar_nombre_con_cache_caida_persiste_y_registra_warning(
    servicio_con_cache_caida, repositorio, caplog
):
    guardado = await guardar_documento_anterior(repositorio)

    await servicio_con_cache_caida.actualizar_nombre(guardado.id, nombre="nuevo.pdf")

    persistido = await repositorio.get_by_id(guardado.id)
    assert persistido.nombre == "nuevo.pdf"
    assert hay_warning_con(caplog, f"pdf:id:{guardado.id}")


async def test_eliminar_con_cache_caida_borra_y_registra_warning(
    servicio_con_cache_caida, repositorio, caplog
):
    guardado = await guardar_documento_anterior(repositorio)

    await servicio_con_cache_caida.eliminar(guardado.id)

    assert await repositorio.get_by_id(guardado.id) is None
    assert hay_warning_con(caplog, f"pdf:id:{guardado.id}")
