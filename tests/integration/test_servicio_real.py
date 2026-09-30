"""El servicio completo por HTTP, con el lifespan real: MongoDB, Redis y lock reales.

Se saltea sin TEST_MONGO_URI y TEST_REDIS_URL (vía las fixtures coleccion_mongo
y cliente_redis). A diferencia de los tests de la capa HTTP, acá no hay dobles:
se verifica la integración de todas las piezas (contrato, sección 7).
"""

import os
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app, lifespan

pytestmark = pytest.mark.asyncio

CLAVES_AJENAS = {"pdf:id:otro-documento", "consultas:otra-cosa"}


def body(**cambios) -> dict:
    datos = {
        "nombre": "contrato.pdf",
        "checksum": uuid4().hex + uuid4().hex,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
    }
    return {**datos, **cambios}


@pytest_asyncio.fixture
async def http(monkeypatch, coleccion_mongo, cliente_redis):
    """Cliente HTTP contra la app armada por su lifespan real."""
    monkeypatch.setenv("MONGO_URI", os.environ["TEST_MONGO_URI"])
    monkeypatch.setenv("MONGO_DATABASE", coleccion_mongo.database.name)
    monkeypatch.setenv("MONGO_COLLECTION", coleccion_mongo.name)
    monkeypatch.setenv("REDIS_URL", os.environ["TEST_REDIS_URL"])
    monkeypatch.setenv("LOCK_TIMEOUT_SECONDS", "2")
    async with lifespan(app):
        transporte = ASGITransport(app=app)
        async with AsyncClient(transport=transporte, base_url="http://test") as c:
            yield c


async def _cachear(redis, *claves: str) -> None:
    """Simula lo que persistencia-consultas dejó en la caché."""
    for clave in (*claves, *CLAVES_AJENAS):
        await redis.set(clave, "{}")


async def _claves(redis) -> set[str]:
    return {clave async for clave in redis.scan_iter("*")}


async def test_post_invalida_checksum_y_listados_en_redis_real(http, cliente_redis):
    datos = body()
    await _cachear(
        cliente_redis, f"pdf:checksum:{datos['checksum']}", "pdf:list:p=1", "pdf:list:p=2"
    )

    respuesta = await http.post("/pdf", json=datos)

    assert respuesta.status_code == 201
    assert await _claves(cliente_redis) == CLAVES_AJENAS


async def test_patch_invalida_id_checksum_y_listados_en_redis_real(http, cliente_redis):
    creado = (await http.post("/pdf", json=body())).json()
    await _cachear(
        cliente_redis,
        f"pdf:id:{creado['id']}",
        f"pdf:checksum:{creado['checksum']}",
        "pdf:list:p=1",
    )

    respuesta = await http.patch(f"/pdf/{creado['id']}", json={"nombre": "nuevo.pdf"})

    assert respuesta.status_code == 200
    assert await _claves(cliente_redis) == CLAVES_AJENAS


async def test_delete_invalida_id_checksum_y_listados_en_redis_real(
    http, cliente_redis
):
    creado = (await http.post("/pdf", json=body())).json()
    await _cachear(
        cliente_redis,
        f"pdf:id:{creado['id']}",
        f"pdf:checksum:{creado['checksum']}",
        "pdf:list:p=1",
    )

    respuesta = await http.delete(f"/pdf/{creado['id']}")

    assert respuesta.status_code == 204
    assert await _claves(cliente_redis) == CLAVES_AJENAS
