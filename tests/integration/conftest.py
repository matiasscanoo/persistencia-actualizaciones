"""Fixtures de adaptadores reales.

Los tests que las usan se saltean si no está definida la variable del servicio,
así la suite sigue corriendo sin MongoDB ni Redis.
"""

import os
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.database import crear_cliente_mongo, crear_cliente_redis
from app.core.dependencies import get_documento_service
from app.core.memory_cache import InMemoryCache
from app.core.memory_lock import InMemoryLock
from app.core.memory_repository import InMemoryRepository
from app.core.mongo_repository import MongoRepository
from app.main import app
from app.services.documento_service import DocumentoService

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


@pytest.fixture
def cache_en_memoria() -> InMemoryCache:
    return InMemoryCache()


@pytest.fixture
def lock_en_memoria() -> InMemoryLock:
    return InMemoryLock()


@pytest.fixture
def cliente_http(repositorio_en_memoria, cache_en_memoria, lock_en_memoria):
    """TestClient con dobles en memoria; no ejecuta el lifespan real de main.py.

    Expone el doble de caché como `.cache` para verificar qué claves quedaron
    invalidadas tras un request.
    """
    servicio = DocumentoService(
        repositorio_en_memoria, cache_en_memoria, lock_en_memoria
    )
    app.dependency_overrides[get_documento_service] = lambda: servicio
    cliente = TestClient(app)
    cliente.cache = cache_en_memoria
    yield cliente
    app.dependency_overrides.clear()


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
