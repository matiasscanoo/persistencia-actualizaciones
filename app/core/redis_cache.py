"""Implementación de Cache sobre Redis: solo invalida (contrato, sección 7.1)."""

from redis.asyncio import Redis

from app.core.cache import Cache
from app.core.database import ERRORES_DE_CONEXION_REDIS
from app.core.exceptions import CacheUnavailableError

# Claves por lote de SCAN y de UNLINK.
TAMANO_DE_LOTE = 500


class RedisCache(Cache):
    """Borra claves exactas con UNLINK y patrones con SCAN + UNLINK, nunca KEYS."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def invalidate(self, keys: list[str]) -> None:
        exactas = [clave for clave in keys if not clave.endswith("*")]
        patrones = [clave for clave in keys if clave.endswith("*")]
        try:
            if exactas:
                await self._client.unlink(*exactas)
            for patron in patrones:
                await self._borrar_patron(patron)
        except ERRORES_DE_CONEXION_REDIS as error:
            raise CacheUnavailableError(str(error)) from error

    async def _borrar_patron(self, patron: str) -> None:
        lote: list[str] = []
        async for clave in self._client.scan_iter(match=patron, count=TAMANO_DE_LOTE):
            lote.append(clave)
            if len(lote) == TAMANO_DE_LOTE:
                await self._client.unlink(*lote)
                lote = []
        if lote:
            await self._client.unlink(*lote)
