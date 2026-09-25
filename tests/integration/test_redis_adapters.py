"""Tests propios de RedisCache y RedisLock: SCAN, expiración, espera y caídas."""

import asyncio

import pytest

from app.core.exceptions import CacheUnavailableError, LockUnavailableError
from app.core.redis_cache import RedisCache
from app.core.redis_lock import RedisLock

pytestmark = pytest.mark.asyncio

CLAVE = "lock:pdf:id:uno"


@pytest.mark.integration
async def test_invalida_todas_las_claves_de_un_patron_grande(cliente_redis):
    listados = {f"pdf:list:pagina={n}": "valor" for n in range(1500)}
    await cliente_redis.mset({**listados, "pdf:id:otro": "valor"})

    await RedisCache(cliente_redis).invalidate(["pdf:list:*"])

    assert set(await cliente_redis.keys("*")) == {"pdf:id:otro"}


@pytest.mark.integration
async def test_el_lock_se_guarda_con_expiracion(cliente_redis):
    await RedisLock(cliente_redis, timeout_seconds=0.2).acquire(CLAVE)

    assert 0 < await cliente_redis.pttl(CLAVE) <= 200


@pytest.mark.integration
async def test_el_lock_vence_solo_despues_del_timeout(cliente_redis):
    lock = RedisLock(cliente_redis, timeout_seconds=0.2)
    await lock.acquire(CLAVE)

    await asyncio.sleep(0.3)

    assert await lock.acquire(CLAVE)


@pytest.mark.integration
async def test_acquire_espera_a_que_el_otro_libere(cliente_redis):
    lock = RedisLock(cliente_redis, timeout_seconds=1)
    token = await lock.acquire(CLAVE)

    async def liberar_enseguida() -> None:
        await asyncio.sleep(0.1)
        await lock.release(CLAVE, token)

    liberacion = asyncio.create_task(liberar_enseguida())

    assert await lock.acquire(CLAVE)
    await liberacion


async def test_cache_con_redis_caido_lanza_cache_unavailable(cliente_redis_caido):
    with pytest.raises(CacheUnavailableError):
        await RedisCache(cliente_redis_caido).invalidate(["pdf:list:*"])


async def test_lock_con_redis_caido_lanza_lock_unavailable(cliente_redis_caido):
    with pytest.raises(LockUnavailableError):
        await RedisLock(cliente_redis_caido, timeout_seconds=1).acquire(CLAVE)


async def test_liberar_con_redis_caido_no_falla(cliente_redis_caido):
    await RedisLock(cliente_redis_caido, timeout_seconds=1).release(CLAVE, "token")
