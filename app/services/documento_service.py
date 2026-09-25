"""Reglas de negocio de escritura de documentos PDF (sin FastAPI)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.core.cache import Cache
from app.core.exceptions import (
    CacheUnavailableError,
    LockUnavailableError,
    ResourceNotFoundError,
)
from app.core.lock import Lock
from app.core.repository import Repository
from app.models.documento_pdf import DocumentoPdf

logger = logging.getLogger(__name__)


class DocumentoService:
    """Crea, modifica y elimina documentos PDF y deja la caché coherente.

    Cada escritura sigue el orden: lock → escritura → invalidación → liberar.
    """

    def __init__(
        self, repository: Repository[DocumentoPdf], cache: Cache, lock: Lock
    ) -> None:
        self._repository = repository
        self._cache = cache
        self._lock = lock

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
        async with self._con_lock(f"lock:pdf:checksum:{checksum}"):
            creado = await self._repository.add(documento)
            await self._invalidar(creado)
        return creado

    async def actualizar_nombre(
        self, documento_id: str, *, nombre: str
    ) -> DocumentoPdf:
        """Cambia el nombre y renueva `updated_at`; el resto no se toca."""
        async with self._con_lock(f"lock:pdf:id:{documento_id}"):
            documento = await self._repository.get_by_id(documento_id)
            if documento is None:
                raise ResourceNotFoundError(documento_id)
            documento.nombre = nombre
            documento.update_timestamp()
            actualizado = await self._repository.update(documento)
            await self._invalidar(actualizado)
        return actualizado

    async def eliminar(self, documento_id: str) -> None:
        """Borra el documento; un id inexistente o ya borrado es un error (A6)."""
        async with self._con_lock(f"lock:pdf:id:{documento_id}"):
            eliminado = await self._repository.delete(documento_id)
            if eliminado is None:
                raise ResourceNotFoundError(documento_id)
            await self._invalidar(eliminado)

    @asynccontextmanager
    async def _con_lock(self, clave: str) -> AsyncIterator[None]:
        """Ejecuta el bloque con el lock tomado y lo libera siempre al salir.

        Si el lock no responde, el bloque se ejecuta igual (fail-open): la
        unicidad la sigue garantizando el índice único de MongoDB.
        """
        try:
            token = await self._lock.acquire(clave)
        except LockUnavailableError:
            logger.warning("Lock no disponible; se escribe sin lock: %s", clave)
            yield
            return
        try:
            yield
        finally:
            await self._lock.release(clave, token)

    async def _invalidar(self, documento: DocumentoPdf) -> None:
        """Borra de la caché lo que depende del documento, tras escribir en Mongo.

        Si la caché no responde, la escritura ya hecha se mantiene (fail-open).
        """
        claves = [
            f"pdf:id:{documento.id}",
            f"pdf:checksum:{documento.checksum}",
            "pdf:list:*",
        ]
        try:
            await self._cache.invalidate(claves)
        except CacheUnavailableError:
            logger.warning(
                "Caché no disponible; quedan sin invalidar: %s", ", ".join(claves)
            )
