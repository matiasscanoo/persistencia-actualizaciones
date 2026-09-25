"""Suite de contrato de Lock: la misma para memoria y Redis (LSP)."""

from dataclasses import dataclass

import pytest

from app.core.exceptions import LockTimeoutError
from app.core.lock import Lock
from app.core.memory_lock import InMemoryLock
from app.core.redis_lock import RedisLock

pytestmark = pytest.mark.asyncio

CLAVE = "lock:pdf:id:uno"


@dataclass
class LockBajoPrueba:
    """El lock a probar y otro proceso que comparte el mismo almacenamiento.

    El lock de `otro_proceso` dura más que la espera de `lock`: así una clave
    tomada sigue tomada durante toda la espera (en Redis, el lock vence solo).
    """

    lock: Lock
    otro_proceso: Lock


@pytest.fixture
def lock_en_memoria() -> LockBajoPrueba:
    lock = InMemoryLock()
    return LockBajoPrueba(lock=lock, otro_proceso=lock)


@pytest.fixture
def lock_redis(cliente_redis) -> LockBajoPrueba:
    return LockBajoPrueba(
        lock=RedisLock(cliente_redis, timeout_seconds=0.2),
        otro_proceso=RedisLock(cliente_redis, timeout_seconds=5),
    )


@pytest.fixture(
    params=[
        "lock_en_memoria",
        pytest.param("lock_redis", marks=pytest.mark.integration),
    ],
    ids=["memoria", "redis"],
)
def bajo_prueba(request) -> LockBajoPrueba:
    return request.getfixturevalue(request.param)


async def test_acquire_devuelve_un_token(bajo_prueba):
    token = await bajo_prueba.lock.acquire(CLAVE)

    assert isinstance(token, str) and token


async def test_una_clave_tomada_por_otro_lanza_lock_timeout(bajo_prueba):
    await bajo_prueba.otro_proceso.acquire(CLAVE)

    with pytest.raises(LockTimeoutError) as error:
        await bajo_prueba.lock.acquire(CLAVE)

    assert error.value.key == CLAVE


async def test_release_libera_la_clave(bajo_prueba):
    token = await bajo_prueba.lock.acquire(CLAVE)

    await bajo_prueba.lock.release(CLAVE, token)

    assert await bajo_prueba.lock.acquire(CLAVE)


async def test_release_con_otro_token_no_libera_la_clave(bajo_prueba):
    await bajo_prueba.otro_proceso.acquire(CLAVE)

    await bajo_prueba.lock.release(CLAVE, "token-de-otro")

    with pytest.raises(LockTimeoutError):
        await bajo_prueba.lock.acquire(CLAVE)


async def test_claves_distintas_son_independientes(bajo_prueba):
    await bajo_prueba.otro_proceso.acquire(CLAVE)

    assert await bajo_prueba.lock.acquire("lock:pdf:id:dos")
