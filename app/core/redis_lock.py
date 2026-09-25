"""Implementación de Lock sobre Redis: SET NX PX con token y liberación con Lua."""

import asyncio
import logging
import time
from uuid import uuid4

from redis.asyncio import Redis

from app.core.database import ERRORES_DE_CONEXION_REDIS
from app.core.exceptions import LockTimeoutError, LockUnavailableError
from app.core.lock import Lock

logger = logging.getLogger(__name__)

# Borra la clave solo si todavía guarda el token de quien la libera: así nadie
# libera un lock que venció y ya tomó otro proceso.
LIBERAR_SI_ES_DEL_DUENO = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""

ESPERA_ENTRE_INTENTOS_S = 0.05


class RedisLock(Lock):
    """Lock por clave con expiración y espera máxima de `timeout_seconds`.

    El mismo valor es la expiración del lock (PX) y el tiempo máximo que se
    reintenta obtenerlo (LOCK_TIMEOUT_SECONDS, contrato sección 7.2).
    """

    def __init__(self, client: Redis, timeout_seconds: float) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._liberar = client.register_script(LIBERAR_SI_ES_DEL_DUENO)

    async def acquire(self, key: str) -> str:
        token = str(uuid4())
        expiracion_ms = int(self._timeout_seconds * 1000)
        limite = time.monotonic() + self._timeout_seconds
        try:
            while not await self._client.set(key, token, nx=True, px=expiracion_ms):
                if time.monotonic() >= limite:
                    raise LockTimeoutError(key)
                await asyncio.sleep(ESPERA_ENTRE_INTENTOS_S)
        except ERRORES_DE_CONEXION_REDIS as error:
            raise LockUnavailableError(str(error)) from error
        return token

    async def release(self, key: str, token: str) -> None:
        try:
            await self._liberar(keys=[key], args=[token])
        except ERRORES_DE_CONEXION_REDIS:
            logger.warning(
                "Redis no disponible; el lock %s vence solo por su expiración", key
            )
