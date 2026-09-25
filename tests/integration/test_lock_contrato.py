"""Suite de contrato de Lock: la misma para memoria y Redis (LSP)."""

import pytest

from app.core.exceptions import LockTimeoutError
from app.core.memory_lock import InMemoryLock
from app.core.redis_lock import RedisLock

pytestmark = pytest.mark.asyncio

CLAVE = "lock:pdf:id:uno"


@pytest.fixture
def lock_en_memoria() -> InMemoryLock:
    return InMemoryLock()


@pytest.fixture
def lock_redis(cliente_redis) -> RedisLock:
    return RedisLock(cliente_redis, timeout_seconds=0.2)


@pytest.fixture(
    params=[
        "lock_en_memoria",
        pytest.param("lock_redis", marks=pytest.mark.integration),
    ],
    ids=["memoria", "redis"],
)
def lock(request):
    return request.getfixturevalue(request.param)


async def test_acquire_devuelve_un_token(lock):
    token = await lock.acquire(CLAVE)

    assert isinstance(token, str) and token


async def test_una_clave_tomada_lanza_lock_timeout(lock):
    await lock.acquire(CLAVE)

    with pytest.raises(LockTimeoutError) as error:
        await lock.acquire(CLAVE)

    assert error.value.key == CLAVE


async def test_release_libera_la_clave(lock):
    token = await lock.acquire(CLAVE)

    await lock.release(CLAVE, token)

    assert await lock.acquire(CLAVE)


async def test_release_con_otro_token_no_libera_la_clave(lock):
    await lock.acquire(CLAVE)

    await lock.release(CLAVE, "token-de-otro")

    with pytest.raises(LockTimeoutError):
        await lock.acquire(CLAVE)


async def test_claves_distintas_son_independientes(lock):
    await lock.acquire(CLAVE)

    assert await lock.acquire("lock:pdf:id:dos")
