import asyncio

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.dependencia import Dependencia

# Contrato 1.2.0: cada chequeo de /health tarda como máximo 1 s. El cliente de
# MongoDB espera hasta 5 s a un servidor (MONGO_TIMEOUT_MS), así que el ping se
# corta acá.
TIMEOUT_SEGUNDOS = 1.0


class MongoDependencia(Dependencia):
    def __init__(
        self, cliente: AsyncIOMotorClient, timeout_segundos: float = TIMEOUT_SEGUNDOS
    ) -> None:
        self._cliente = cliente
        self._timeout_segundos = timeout_segundos

    async def disponible(self) -> bool:
        try:
            await asyncio.wait_for(
                self._cliente.admin.command("ping"), self._timeout_segundos
            )
        except (asyncio.TimeoutError, PyMongoError):
            return False
        return True


class RedisDependencia(Dependencia):
    """El cliente Redis ya tiene timeouts de 1 s y no reintenta (core/database.py)."""

    def __init__(self, cliente: Redis) -> None:
        self._cliente = cliente

    async def disponible(self) -> bool:
        try:
            await self._cliente.ping()
        except RedisError:
            return False
        return True
