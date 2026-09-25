"""Fixtures de adaptadores reales.

Los tests que las usan se saltean si no está definida la variable del servicio,
así la suite sigue corriendo sin MongoDB ni Redis.
"""

import os
from uuid import uuid4

import pytest
import pytest_asyncio

from app.core.database import crear_cliente_mongo, crear_cliente_redis
from app.core.memory_repository import InMemoryRepository
from app.core.mongo_repository import MongoRepository

TEST_MONGO_URI = os.environ.get("TEST_MONGO_URI")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL")


@pytest_asyncio.fixture
async def coleccion_mongo():
    """Colección descartable en un MongoDB real, borrada al terminar el test."""
    if not TEST_MONGO_URI:
        pytest.skip("TEST_MONGO_URI no definida")
    cliente = crear_cliente_mongo(TEST_MONGO_URI)
    coleccion = cliente["persistencia_actualizaciones_test"][f"doc_{uuid4().hex}"]
    yield coleccion
    await coleccion.drop()
    cliente.close()


@pytest.fixture
def repositorio_en_memoria() -> InMemoryRepository:
    return InMemoryRepository()


@pytest_asyncio.fixture
async def repositorio_mongo(coleccion_mongo) -> MongoRepository:
    repositorio = MongoRepository(coleccion_mongo)
    await repositorio.crear_indices()
    return repositorio


@pytest_asyncio.fixture
async def cliente_redis():
    """Redis real y descartable: la base se vacía antes y después del test."""
    if not TEST_REDIS_URL:
        pytest.skip("TEST_REDIS_URL no definida")
    cliente = crear_cliente_redis(TEST_REDIS_URL)
    await cliente.flushdb()
    yield cliente
    await cliente.flushdb()
    await cliente.aclose()


@pytest_asyncio.fixture
async def cliente_redis_caido():
    """Cliente apuntando a un puerto cerrado, con timeout corto: Redis caído."""
    cliente = crear_cliente_redis("redis://127.0.0.1:1", timeout_s=0.1)
    yield cliente
    await cliente.aclose()
