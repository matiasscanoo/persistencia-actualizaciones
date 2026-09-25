"""Implementación de Repository sobre MongoDB con Motor."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from app.core.exceptions import DatabaseError, DuplicateChecksumError
from app.core.repository import Repository
from app.models.documento_pdf import DocumentoPdf


class MongoRepository(Repository[DocumentoPdf]):
    """Documentos en una colección con `_id` UUID string e índice único en checksum.

    La colección es compartida con persistencia-consultas (contrato, sección 8).
    """

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._collection = collection

    async def crear_indices(self) -> None:
        """Crea el índice único de `checksum`; es idempotente y se llama al arrancar."""
        async with _errores_de_mongo():
            await self._collection.create_index("checksum", unique=True)

    async def add(self, entity: DocumentoPdf) -> DocumentoPdf:
        async with _errores_de_mongo():
            try:
                await self._collection.insert_one(_a_documento(entity))
            except DuplicateKeyError as error:
                raise DuplicateChecksumError(entity.checksum) from error
        return entity

    async def get_by_id(self, entity_id: str) -> DocumentoPdf | None:
        async with _errores_de_mongo():
            documento = await self._collection.find_one({"_id": entity_id})
        return _a_entidad(documento) if documento else None

    async def update(self, entity: DocumentoPdf) -> DocumentoPdf:
        async with _errores_de_mongo():
            await self._collection.replace_one({"_id": entity.id}, _a_documento(entity))
        return entity

    async def delete(self, entity_id: str) -> DocumentoPdf | None:
        async with _errores_de_mongo():
            documento = await self._collection.find_one_and_delete({"_id": entity_id})
        return _a_entidad(documento) if documento else None


@asynccontextmanager
async def _errores_de_mongo() -> AsyncIterator[None]:
    """Traduce la falta de conexión con Mongo a DatabaseError (503)."""
    try:
        yield
    except ConnectionFailure as error:
        raise DatabaseError() from error


def _a_documento(entidad: DocumentoPdf) -> dict:
    """Entidad → documento Mongo (`id` → `_id`)."""
    documento = asdict(entidad)
    documento["_id"] = documento.pop("id")
    return documento


def _a_entidad(documento: dict) -> DocumentoPdf:
    """Documento Mongo → entidad (`_id` → `id`)."""
    documento["id"] = documento.pop("_id")
    return DocumentoPdf(**documento)
