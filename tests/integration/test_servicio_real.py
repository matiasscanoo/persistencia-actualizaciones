"""El servicio completo por HTTP, con el lifespan real: MongoDB, Redis y lock reales.

Se saltea sin TEST_MONGO_URI y TEST_REDIS_URL (vía las fixtures coleccion_mongo
y cliente_redis). A diferencia de los tests de la capa HTTP, acá no hay dobles:
se verifica la integración de todas las piezas (contrato, sección 7).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.logging_context import CorrelationIdFilter
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


@asynccontextmanager
async def _servicio(monkeypatch, coleccion_mongo, redis_url: str):
    """Cliente HTTP contra la app armada por su lifespan real."""
    monkeypatch.setenv("MONGO_URI", os.environ["TEST_MONGO_URI"])
    monkeypatch.setenv("MONGO_DATABASE", coleccion_mongo.database.name)
    monkeypatch.setenv("MONGO_COLLECTION", coleccion_mongo.name)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("LOCK_TIMEOUT_SECONDS", "2")
    async with lifespan(app):
        transporte = ASGITransport(app=app)
        async with AsyncClient(transport=transporte, base_url="http://test") as c:
            yield c


@pytest_asyncio.fixture
async def http(monkeypatch, coleccion_mongo, cliente_redis):
    async with _servicio(
        monkeypatch, coleccion_mongo, os.environ["TEST_REDIS_URL"]
    ) as c:
        yield c


@pytest_asyncio.fixture
async def http_con_redis_caido(monkeypatch, coleccion_mongo):
    """Mongo real y Redis apuntando a un puerto cerrado."""
    async with _servicio(monkeypatch, coleccion_mongo, "redis://127.0.0.1:1/0") as c:
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
        cliente_redis,
        f"pdf:checksum:{datos['checksum']}",
        "pdf:list:p=1",
        "pdf:list:p=2",
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


async def test_post_repetido_tras_un_timeout_responde_409_y_no_duplica(
    http, coleccion_mongo
):
    datos = body()

    primero = await http.post("/pdf", json=datos)
    reintento = await http.post("/pdf", json=datos)

    assert (primero.status_code, reintento.status_code) == (201, 409)
    assert reintento.json()["error"]["code"] == "DUPLICATE_CHECKSUM"
    assert await coleccion_mongo.count_documents({"checksum": datos["checksum"]}) == 1


async def test_compensacion_saga_borra_y_el_delete_repetido_responde_404(
    http, coleccion_mongo
):
    creado = (await http.post("/pdf", json=body())).json()

    compensacion = await http.delete(f"/pdf/{creado['id']}")
    repetida = await http.delete(f"/pdf/{creado['id']}")

    assert compensacion.status_code == 204
    assert repetida.status_code == 404
    assert repetida.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert await coleccion_mongo.count_documents({"_id": creado["id"]}) == 0


async def test_posts_concurrentes_con_el_mismo_checksum_crean_un_solo_documento(
    http, coleccion_mongo, cliente_redis
):
    datos = body()

    respuestas = await asyncio.gather(
        *(http.post("/pdf", json={**datos, "nombre": f"{i}.pdf"}) for i in range(10))
    )

    codigos = [r.status_code for r in respuestas]
    assert codigos.count(201) == 1
    assert set(codigos) <= {201, 409, 503}
    assert await coleccion_mongo.count_documents({"checksum": datos["checksum"]}) == 1
    assert await _claves(cliente_redis) == set()


async def test_patches_concurrentes_dejan_la_ultima_escritura_y_sin_cache_vieja(
    http, coleccion_mongo, cliente_redis
):
    creado = (await http.post("/pdf", json=body())).json()
    await _cachear(
        cliente_redis, f"pdf:id:{creado['id']}", f"pdf:checksum:{creado['checksum']}"
    )

    respuestas = await asyncio.gather(
        *(
            http.patch(f"/pdf/{creado['id']}", json={"nombre": f"v{i}.pdf"})
            for i in range(10)
        )
    )

    assert {r.status_code for r in respuestas} <= {200, 503}
    exitosas = [r.json() for r in respuestas if r.status_code == 200]
    ultima = max(d["updated_at"] for d in exitosas)
    guardado = await coleccion_mongo.find_one({"_id": creado["id"]})
    assert guardado["nombre"] in {
        d["nombre"] for d in exitosas if d["updated_at"] == ultima
    }
    assert await _claves(cliente_redis) == CLAVES_AJENAS


async def test_con_redis_caido_la_escritura_sigue_y_el_warning_lleva_el_correlation_id(
    http_con_redis_caido, coleccion_mongo, caplog
):
    caplog.handler.addFilter(CorrelationIdFilter())
    caplog.set_level(logging.WARNING, logger="app.services.documento_service")
    datos = body()

    respuesta = await http_con_redis_caido.post(
        "/pdf", json=datos, headers={"X-Correlation-ID": "e2e-redis-caido"}
    )

    assert respuesta.status_code == 201
    assert await coleccion_mongo.count_documents({"checksum": datos["checksum"]}) == 1
    avisos = [r for r in caplog.records if r.name == "app.services.documento_service"]
    assert len(avisos) == 2  # sin lock y sin invalidación
    assert {r.correlation_id for r in avisos} == {"e2e-redis-caido"}
