import asyncio

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from app.core.health_check import HealthCheck

# Contrato 1.2.0: cada chequeo de /health tarda como máximo 1 s. El cliente de
# MongoDB espera hasta 5 s a un servidor (MONGO_TIMEOUT_MS), así que el ping se
# corta acá.
TIMEOUT_SEGUNDOS = 1.0


class MongoHealthCheck(HealthCheck):
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
