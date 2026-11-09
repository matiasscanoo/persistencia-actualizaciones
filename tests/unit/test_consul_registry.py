import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.core.consul_registry import ConsulRegistry


def settings(tmp_path: Path) -> Settings:
    token = tmp_path / "consul.token"
    token.write_text("test-token", encoding="utf-8")
    return Settings(
        _env_file=None,
        mongo_uri="mongodb://mongo:27017",
        mongo_database="pdfs",
        mongo_collection="pdfs",
        redis_url="redis://redis:6379/0",
        lock_timeout_seconds=5,
        consul_enabled=True,
        consul_http_addr="http://consul:8500",
        consul_http_token_file=str(token),
        consul_service_address="persistencia-actualizaciones",
        consul_service_port=8000,
    )


@pytest.mark.asyncio
async def test_register_and_deregister_persistencia_actualizaciones(tmp_path: Path):
    requests = []

    async def responder(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    registry = ConsulRegistry(
        settings=settings(tmp_path),
        instance_id="persistencia-actualizaciones-instance-a",
        transport=httpx.MockTransport(responder),
    )

    await registry.register()
    await registry.deregister()

    payload = json.loads(requests[0].content)
    assert requests[0].headers["X-Consul-Token"] == "test-token"
    assert payload["ID"] == "persistencia-actualizaciones-instance-a"
    assert payload["Name"] == "persistencia-actualizaciones"
    assert payload["Address"] == "persistencia-actualizaciones"
    assert payload["Port"] == 8000
    assert (
        payload["Checks"][0]["HTTP"]
        == "http://persistencia-actualizaciones:8000/health"
    )
    # Servicio interno (contrato: solo el orquestador es público): sin etiquetas de
    # Traefik, así Consul Catalog no lo publica.
    assert not [tag for tag in payload["Tags"] if tag.startswith("traefik")]
    assert str(requests[1].url).endswith(
        "/v1/agent/service/deregister/persistencia-actualizaciones-instance-a"
    )


def _consul(
    tmp_path: Path, registrado: list[bool], requests: list, caidas: int = 0
) -> ConsulRegistry:
    """ConsulRegistry contra un agente simulado: `registrado[0]` dice si la instancia
    figura en Consul y un register la vuelve a anotar. Las primeras `caidas`
    requests fallan como si Consul no respondiera."""
    pendientes = [caidas]

    async def responder(request: httpx.Request) -> httpx.Response:
        if pendientes[0]:
            pendientes[0] -= 1
            raise httpx.ConnectError("Consul no responde")
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200 if registrado[0] else 404)
        if request.url.path == "/v1/agent/service/register":
            registrado[0] = True
        return httpx.Response(200)

    return ConsulRegistry(
        settings=settings(tmp_path),
        instance_id="persistencia-actualizaciones-instance-a",
        transport=httpx.MockTransport(responder),
    )


@pytest.mark.asyncio
async def test_se_vuelve_a_registrar_si_consul_lo_dio_de_baja(tmp_path: Path):
    # Con MongoDB caído más de DeregisterCriticalServiceAfter, Consul borra la
    # instancia; al volver MongoDB tiene que reaparecer sin reiniciar el contenedor.
    requests = []
    registry = _consul(tmp_path, [False], requests)

    assert await registry.ensure_registered() is True

    assert str(requests[0].url).endswith(
        "/v1/agent/service/persistencia-actualizaciones-instance-a"
    )
    assert requests[1].url.path == "/v1/agent/service/register"


@pytest.mark.asyncio
async def test_no_se_vuelve_a_registrar_si_sigue_en_consul(tmp_path: Path):
    requests = []
    registry = _consul(tmp_path, [True], requests)

    assert await registry.ensure_registered() is False

    assert [r.method for r in requests] == ["GET"]


@pytest.mark.asyncio
async def test_mantiene_el_registro_aunque_consul_no_responda_un_rato(tmp_path: Path):
    requests = []
    registrado = [False]
    registry = _consul(tmp_path, registrado, requests, caidas=2)

    async def hasta_reaparecer() -> None:
        while not registrado[0]:
            await asyncio.sleep(0.01)

    tarea = asyncio.create_task(registry.keep_registered(intervalo_segundos=0.01))
    try:
        # Si un error de conexión cortara el ciclo, la instancia no reaparecería.
        await asyncio.wait_for(hasta_reaparecer(), timeout=2)
    finally:
        tarea.cancel()
