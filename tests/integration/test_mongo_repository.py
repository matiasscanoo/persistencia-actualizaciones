"""Tests propios de MongoRepository: esquema en Mongo (sección 8) y errores."""

from datetime import datetime

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.database import crear_cliente_mongo
from app.core.exceptions import DatabaseError
from app.core.mongo_repository import MongoRepository
from app.models.documento_pdf import DocumentoPdf

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def documento(**cambios) -> DocumentoPdf:
    datos = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": None,
    }
    return DocumentoPdf(**{**datos, **cambios})


def test_el_cliente_mongo_devuelve_fechas_con_zona_horaria():
    cliente = crear_cliente_mongo("mongodb://127.0.0.1:1")

    assert cliente.codec_options.tz_aware is True
    cliente.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_guarda_el_esquema_compartido_con_consultas(
    repositorio_mongo, coleccion_mongo
):
    guardado = await repositorio_mongo.add(documento())

    crudo = await coleccion_mongo.find_one({"_id": guardado.id})

    assert set(crudo) == {
        "_id",
        "nombre",
        "checksum",
        "texto",
        "tamano_bytes",
        "paginas",
        "created_at",
        "updated_at",
    }
    assert isinstance(crudo["_id"], str)
    assert crudo["paginas"] is None
    assert isinstance(crudo["created_at"], datetime)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_crear_indices_es_idempotente_y_crea_el_indice_unico(
    repositorio_mongo, coleccion_mongo
):
    await repositorio_mongo.crear_indices()

    indices = await coleccion_mongo.index_information()

    assert indices["checksum_1"]["key"] == [("checksum", 1)]
    assert indices["checksum_1"]["unique"] is True


@pytest.fixture
def repositorio_sin_mongo():
    """Repositorio apuntando a un puerto cerrado: Mongo no disponible."""
    cliente = AsyncIOMotorClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=100)
    yield MongoRepository(cliente["db"]["documentos"])
    cliente.close()


@pytest.mark.parametrize(
    "operacion",
    [
        lambda repo: repo.add(documento()),
        lambda repo: repo.get_by_id("un-id"),
        lambda repo: repo.update(documento()),
        lambda repo: repo.delete("un-id"),
    ],
    ids=["add", "get_by_id", "update", "delete"],
)
@pytest.mark.asyncio
async def test_mongo_no_disponible_lanza_database_error(
    repositorio_sin_mongo, operacion
):
    with pytest.raises(DatabaseError) as error:
        await operacion(repositorio_sin_mongo)

    assert error.value.error_code == "DATABASE_ERROR"
