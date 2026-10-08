"""Tests de CorrelationIdFilter y de configurar_logs (logging.json, contrato 1.2.0)."""

import logging
import sys

import pytest

from app.core.logging_context import (
    CorrelationIdFilter,
    configurar_logs,
    correlation_id_var,
)


@pytest.fixture
def logging_restaurado():
    """configurar_logs reemplaza los handlers del root: se restauran al terminar."""
    root = logging.getLogger()
    handlers, nivel = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(nivel)


def test_filter_agrega_el_correlation_id_del_contexto_al_record() -> None:
    token = correlation_id_var.set("cid-de-prueba")
    try:
        record = logging.LogRecord("app", logging.INFO, __file__, 1, "msg", None, None)
        resultado = CorrelationIdFilter().filter(record)
    finally:
        correlation_id_var.reset(token)

    assert resultado is True
    assert record.correlation_id == "cid-de-prueba"


def test_filter_usa_el_valor_por_defecto_sin_correlation_id_en_contexto() -> None:
    record = logging.LogRecord("app", logging.INFO, __file__, 1, "msg", None, None)

    CorrelationIdFilter().filter(record)

    assert record.correlation_id == "-"


def test_el_handler_escribe_en_stdout(logging_restaurado) -> None:
    # 12-Factor XI: los logs son un flujo de eventos a stdout, no a stderr.
    configurar_logs("INFO")

    assert [h.stream for h in logging.getLogger().handlers] == [sys.stdout]


def test_configurar_logs_aplica_el_nivel(logging_restaurado) -> None:
    configurar_logs("DEBUG")

    assert logging.getLogger().level == logging.DEBUG


def test_cada_linea_lleva_nivel_logger_y_correlation_id(
    logging_restaurado, capsys
) -> None:
    configurar_logs("INFO")
    token = correlation_id_var.set("cid-de-prueba")
    try:
        logging.getLogger("prueba").info("evento clave=valor")
    finally:
        correlation_id_var.reset(token)

    assert "INFO prueba correlation_id=cid-de-prueba evento clave=valor" in (
        capsys.readouterr().out
    )
