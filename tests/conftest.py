"""Fixtures compartidas de la suite (hermética: sin .env, MongoDB ni Redis)."""

import pytest

VARIABLES_DE_ENTORNO = (
    "MONGO_URI",
    "MONGO_DATABASE",
    "MONGO_COLLECTION",
    "REDIS_URL",
    "LOCK_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ningún test hereda variables del entorno de la máquina."""
    for nombre in VARIABLES_DE_ENTORNO:
        monkeypatch.delenv(nombre, raising=False)


@pytest.fixture
def entorno_valido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Variables de entorno mínimas y válidas para construir Settings."""
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo-test:27017")
    monkeypatch.setenv("MONGO_DATABASE", "pdf_test")
    monkeypatch.setenv("MONGO_COLLECTION", "documentos_test")
    monkeypatch.setenv("REDIS_URL", "redis://redis-test:6379/0")
    monkeypatch.setenv("LOCK_TIMEOUT_SECONDS", "5")
