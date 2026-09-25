"""Configuración por variables de entorno (pydantic-settings), validada al arrancar."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables del contrato. Sin defaults: si falta una, la app no arranca.

    REDIS_TTL_SECONDS no se consume: con invalidación el TTL lo aplica
    persistencia-consultas (A7).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str
    mongo_database: str
    mongo_collection: str
    redis_url: str
    lock_timeout_seconds: int = Field(gt=0)
