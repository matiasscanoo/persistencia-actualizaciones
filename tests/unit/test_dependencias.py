import asyncio

import pytest
from pymongo.errors import ServerSelectionTimeoutError
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.dependencias import MongoDependencia, RedisDependencia

pytestmark = pytest.mark.asyncio


class AdminMongo:
    """Doble de cliente.admin de Motor: responde, falla o tarda en el ping."""

    def __init__(self, error: Exception | None = None, demora: float = 0) -> None:
        self._error = error
        self._demora = demora

    async def command(self, nombre: str) -> dict:
        assert nombre == "ping"
        await asyncio.sleep(self._demora)
        if self._error:
            raise self._error
        return {"ok": 1}


class ClienteMongo:
    def __init__(self, admin: AdminMongo) -> None:
        self.admin = admin


class ClienteRedis:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    async def ping(self) -> bool:
        if self._error:
            raise self._error
        return True


async def test_mongo_disponible_si_responde_el_ping():
    assert await MongoDependencia(ClienteMongo(AdminMongo())).disponible()


async def test_mongo_caido_si_el_ping_falla():
    error = ServerSelectionTimeoutError("sin servidor")

    assert not await MongoDependencia(
        ClienteMongo(AdminMongo(error=error))
    ).disponible()


async def test_mongo_caido_si_el_ping_supera_el_timeout():
    lento = ClienteMongo(AdminMongo(demora=1))

    assert not await MongoDependencia(lento, timeout_segundos=0.01).disponible()


async def test_redis_disponible_si_responde_el_ping():
    assert await RedisDependencia(ClienteRedis()).disponible()


async def test_redis_caido_si_el_ping_falla():
    error = RedisConnectionError("sin conexion")

    assert not await RedisDependencia(ClienteRedis(error=error)).disponible()
