"""Reglas de negocio de escritura de documentos PDF (sin FastAPI)."""

from app.core.repository import Repository
from app.models.documento_pdf import DocumentoPdf


class DocumentoService:
    """Crea documentos PDF sobre un repositorio inyectado."""

    def __init__(self, repository: Repository[DocumentoPdf]) -> None:
        self._repository = repository

    async def crear(
        self,
        *,
        nombre: str,
        checksum: str,
        texto: str,
        tamano_bytes: int,
        paginas: int | None,
    ) -> DocumentoPdf:
        """Genera id y fechas y persiste el documento."""
        documento = DocumentoPdf(
            nombre=nombre,
            checksum=checksum,
            texto=texto,
            tamano_bytes=tamano_bytes,
            paginas=paginas,
        )
        return await self._repository.add(documento)
