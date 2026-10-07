import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_lee_las_variables_de_entorno(entorno_valido):
    settings = Settings(_env_file=None)

    assert settings.mongo_uri == "mongodb://mongo-test:27017"
    assert settings.mongo_database == "pdf_test"
    assert settings.mongo_collection == "documentos_test"
    assert settings.redis_url == "redis://redis-test:6379/0"
    assert settings.lock_timeout_seconds == 5


def test_settings_falla_si_falta_mongo_uri(entorno_valido, monkeypatch):
    monkeypatch.delenv("MONGO_URI")

    with pytest.raises(ValidationError, match="mongo_uri"):
        Settings(_env_file=None)


@pytest.mark.parametrize("valor", ["0", "-1"])
def test_settings_falla_si_lock_timeout_no_es_positivo(
    entorno_valido, monkeypatch, valor
):
    monkeypatch.setenv("LOCK_TIMEOUT_SECONDS", valor)

    with pytest.raises(ValidationError, match="lock_timeout_seconds"):
        Settings(_env_file=None)


def test_log_level_es_opcional_e_info_por_defecto(entorno_valido):
    assert Settings(_env_file=None).log_level == "INFO"


def test_log_level_invalido_impide_arrancar(entorno_valido, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError, match="log_level"):
        Settings(_env_file=None)
