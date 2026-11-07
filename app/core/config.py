"""Configuración por variables de entorno o por el KV de Consul (contrato 1.6.0),
validada al arrancar."""

from typing import Literal

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.consul_config import leer_config_de_consul


class ConexionConsul(BaseSettings):
    """Lo único que llega por el entorno cuando hay Consul: cómo conectarse."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    consul_enabled: bool = False
    consul_http_addr: str = "http://consul:8500"
    consul_http_token_file: str | None = None


class Settings(ConexionConsul):
    """Variables del contrato. Sin defaults (salvo LOG_LEVEL, opcional desde el
    contrato 1.2.0): si falta una, la app no arranca.

    REDIS_TTL_SECONDS no se consume: con invalidación el TTL lo aplica
    persistencia-consultas (A7).
    """

    mongo_uri: str
    mongo_database: str
    mongo_collection: str
    redis_url: str
    lock_timeout_seconds: int = Field(gt=0)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    consul_service_address: str | None = None
    consul_service_port: int = 8000


def cargar_settings(transport: httpx.BaseTransport | None = None) -> Settings:
    """Contrato 1.6.0: con CONSUL_ENABLED, la configuración sale del KV de Consul
    (config/persistencia-actualizaciones/) y tiene prioridad sobre el entorno."""
    conexion = ConexionConsul()
    if not conexion.consul_enabled:
        return Settings()
    if not conexion.consul_http_token_file:
        raise ValueError("CONSUL_HTTP_TOKEN_FILE es obligatorio")
    valores = leer_config_de_consul(
        conexion.consul_http_addr,
        conexion.consul_http_token_file,
        "persistencia-actualizaciones",
        transport,
    )
    return Settings(**valores)
