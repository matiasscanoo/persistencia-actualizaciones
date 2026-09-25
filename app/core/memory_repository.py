"""Implementación en memoria de Repository, doble de prueba sin red."""

from copy import copy

from app.core.exceptions import DuplicateChecksumError
from app.core.repository import Repository
from app.models.documento_pdf import DocumentoPdf


class InMemoryRepository(Repository[DocumentoPdf]):
    """Documentos en un diccionario indexado por id.

    Respeta la unicidad de `checksum`, igual que el índice único de MongoDB, y
    guarda y devuelve copias: modificar una entidad no la persiste sin `update`.
    """

    def __init__(self) -> None:
        self._documentos: dict[str, DocumentoPdf] = {}

    async def add(self, entity: DocumentoPdf) -> DocumentoPdf:
        if any(d.checksum == entity.checksum for d in self._documentos.values()):
            raise DuplicateChecksumError(entity.checksum)
        self._documentos[entity.id] = copy(entity)
        return entity

    async def get_by_id(self, entity_id: str) -> DocumentoPdf | None:
        documento = self._documentos.get(entity_id)
        return copy(documento) if documento else None

    async def update(self, entity: DocumentoPdf) -> DocumentoPdf:
        self._documentos[entity.id] = copy(entity)
        return entity
