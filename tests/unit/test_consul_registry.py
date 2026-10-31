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
