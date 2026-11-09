"""Fixtures compartidas de la suite (hermética: sin .env, MongoDB ni Redis)."""

from pathlib import Path

import pytest

VARIABLES_DE_ENTORNO = (
    "MONGO_URI",
    "MONGO_DATABASE",
    "MONGO_COLLECTION",
    "REDIS_URL",
    "LOCK_TIMEOUT_SECONDS",
    "LOG_LEVEL",
    "CONSUL_ENABLED",
    "CONSUL_HTTP_ADDR",
    "CONSUL_HTTP_TOKEN_FILE",
    "CONSUL_SERVICE_ADDRESS",
    "CONSUL_SERVICE_PORT",
)


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ningún test hereda variables de la máquina ni el `.env` del repo.

    Settings lee `.env` del directorio actual: cada test corre en una carpeta
    vacía, así un `.env` local (por ejemplo con CONSUL_ENABLED=true) no cambia
    el resultado.
    """
    for nombre in VARIABLES_DE_ENTORNO:
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def entorno_valido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Variables de entorno mínimas y válidas para construir Settings."""
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo-test:27017")
    monkeypatch.setenv("MONGO_DATABASE", "pdf_test")
    monkeypatch.setenv("MONGO_COLLECTION", "documentos_test")
    monkeypatch.setenv("REDIS_URL", "redis://redis-test:6379/0")
    monkeypatch.setenv("LOCK_TIMEOUT_SECONDS", "5")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: necesita un servicio real (TEST_MONGO_URI o TEST_REDIS_URL); "
        "si la variable no está definida, el test se saltea",
    )
