"""Suite de contrato de Cache: la misma para memoria y Redis (LSP)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pytest

from app.core.cache import Cache
from app.core.memory_cache import InMemoryCache
from app.core.redis_cache import RedisCache

pytestmark = pytest.mark.asyncio


@dataclass
class CacheBajoPrueba:
    """Una caché más la forma de poblarla y leerla desde afuera del puerto."""

    cache: Cache
    poblar: Callable[[set[str]], Awaitable[None]]
    claves: Callable[[], Awaitable[set[str]]]


@pytest.fixture
def cache_en_memoria() -> CacheBajoPrueba:
    cache = InMemoryCache()

    async def poblar(claves: set[str]) -> None:
        cache.claves.update(claves)

    async def claves() -> set[str]:
        return set(cache.claves)

    return CacheBajoPrueba(cache, poblar, claves)


@pytest.fixture
def cache_redis(cliente_redis) -> CacheBajoPrueba:
    async def poblar(claves: set[str]) -> None:
        await cliente_redis.mset({clave: "valor" for clave in claves})

    async def claves() -> set[str]:
        return set(await cliente_redis.keys("*"))

    return CacheBajoPrueba(RedisCache(cliente_redis), poblar, claves)


@pytest.fixture(
    params=[
        "cache_en_memoria",
        pytest.param("cache_redis", marks=pytest.mark.integration),
    ],
    ids=["memoria", "redis"],
)
def bajo_prueba(request) -> CacheBajoPrueba:
    return request.getfixturevalue(request.param)


async def test_invalida_claves_exactas_y_patrones_y_conserva_el_resto(bajo_prueba):
    await bajo_prueba.poblar(
        {
            "pdf:id:uno",
            "pdf:checksum:abc",
            "pdf:list:pagina=1",
            "pdf:list:pagina=2",
            "pdf:id:otro",
            "pdf:checksum:def",
        }
    )

    await bajo_prueba.cache.invalidate(["pdf:id:uno", "pdf:checksum:abc", "pdf:list:*"])

    assert await bajo_prueba.claves() == {"pdf:id:otro", "pdf:checksum:def"}


async def test_invalidar_claves_inexistentes_no_falla(bajo_prueba):
    await bajo_prueba.poblar({"pdf:id:otro"})

    await bajo_prueba.cache.invalidate(["pdf:id:no-esta", "pdf:list:*"])

    assert await bajo_prueba.claves() == {"pdf:id:otro"}
