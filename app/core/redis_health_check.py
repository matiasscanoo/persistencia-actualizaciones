from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.health_check import HealthCheck


class RedisHealthCheck(HealthCheck):
    """El cliente Redis ya tiene timeouts de 1 s y no reintenta (core/database.py)."""

    def __init__(self, cliente: Redis) -> None:
        self._cliente = cliente

    async def disponible(self) -> bool:
        try:
            await self._cliente.ping()
        except RedisError:
            return False
        return True
