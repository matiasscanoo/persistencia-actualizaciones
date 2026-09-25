"""Implementación en memoria de Repository, doble de prueba sin red."""

from app.core.exceptions import DuplicateChecksumError
from app.core.repository import Repository
from app.models.documento_pdf import DocumentoPdf


class InMemoryRepository(Repository[DocumentoPdf]):
    """Documentos en un diccionario indexado por id.

    Respeta la unicidad de `checksum`, igual que el índice único de MongoDB.
    """

    def __init__(self) -> None:
        self._documentos: dict[str, DocumentoPdf] = {}

    async def add(self, entity: DocumentoPdf) -> DocumentoPdf:
        if any(d.checksum == entity.checksum for d in self._documentos.values()):
            raise DuplicateChecksumError(entity.checksum)
        self._documentos[entity.id] = entity
        return entity
