import asyncio
import logging
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Cada cuánto se revisa que la instancia siga en Consul. Consul la borra si su health
# check queda crítico más de DeregisterCriticalServiceAfter (1 min, por ejemplo con
# MongoDB caído); al volver, reaparece en a lo sumo este tiempo.
INTERVALO_DE_REVISION_S = 30


@dataclass(frozen=True)
class ConsulRegistry:
    settings: Settings
    instance_id: str
    transport: httpx.AsyncBaseTransport | None = None

    async def register(self) -> None:
        config = self._validate_config()
        async with self._client(config.token) as client:
            response = await client.put(
                f"{config.address}/v1/agent/service/register",
                json=self._registration_payload(),
            )
            response.raise_for_status()

    async def deregister(self) -> None:
        config = self._validate_config()
        async with self._client(config.token) as client:
            response = await client.put(
                f"{config.address}/v1/agent/service/deregister/{quote(self.instance_id)}"
            )
            response.raise_for_status()

    async def ensure_registered(self) -> bool:
        """Vuelve a registrar la instancia si Consul la dio de baja. Devuelve True si
        tuvo que hacerlo."""
        config = self._validate_config()
        async with self._client(config.token) as client:
            response = await client.get(
                f"{config.address}/v1/agent/service/{quote(self.instance_id)}"
            )
        if response.status_code == 404:
            await self.register()
            return True
        response.raise_for_status()
        return False

    async def keep_registered(self, intervalo_segundos: float) -> None:
        """Revisa el registro cada `intervalo_segundos` hasta que se cancela. Si
        Consul no responde, lo registra en el log y vuelve a intentar."""
        while True:
            await asyncio.sleep(intervalo_segundos)
            try:
                if await self.ensure_registered():
                    logger.warning(
                        "Consul había dado de baja la instancia; se registró"
                    )
            except (httpx.HTTPError, OSError) as error:
                logger.warning("No se pudo revisar el registro en Consul: %s", error)

    def _client(self, token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"X-Consul-Token": token}, timeout=3, transport=self.transport
        )

    def _validate_config(self) -> "ConsulConfig":
        if not self.settings.consul_enabled:
            raise ValueError("Consul registration is disabled")
        if not self.settings.consul_http_token_file:
            raise ValueError("CONSUL_HTTP_TOKEN_FILE is required")
        token = Path(self.settings.consul_http_token_file).read_text().strip()
        if not token:
            raise ValueError("The Consul token file is empty")
        return ConsulConfig(self.settings.consul_http_addr.rstrip("/"), token)

    def _registration_payload(self) -> dict:
        address = self.settings.consul_service_address or socket.gethostbyname(
            socket.gethostname()
        )
        port = self.settings.consul_service_port
        name = "persistencia-actualizaciones"
        return {
            "ID": self.instance_id,
            "Name": name,
            "Address": address,
            "Port": port,
            # Interno: sin etiquetas de Traefik (solo el orquestador es público).
            "Tags": [],
            "Checks": [
                {
                    "Name": "HTTP health check",
                    "HTTP": f"http://{address}:{port}/health",
                    "Interval": "10s",
                    "Timeout": "3s",
                    "DeregisterCriticalServiceAfter": "1m",
                }
            ],
        }


@dataclass(frozen=True)
class ConsulConfig:
    address: str
    token: str
