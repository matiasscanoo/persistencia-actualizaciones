"""Test unitario de CorrelationIdFilter, sin pasar por el pipeline de logging.

logging.basicConfig() en main.py no hace nada bajo pytest porque el plugin de
logging de pytest ya configuró el root logger antes; por eso este test ejercita
el filtro directamente en vez de depender de esa configuración.
"""

import logging
import sys

from app.core.logging_context import (
    CorrelationIdFilter,
    correlation_id_var,
    crear_handler,
)


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


def test_el_handler_escribe_en_stdout() -> None:
    # 12-Factor XI: los logs son un flujo de eventos a stdout, no a stderr.
    handler = crear_handler()

    assert handler.stream is sys.stdout


def test_el_handler_incluye_el_correlation_id_en_cada_linea() -> None:
    handler = crear_handler()
    record = logging.LogRecord("app", logging.INFO, __file__, 1, "msg", None, None)
    token = correlation_id_var.set("cid-de-prueba")
    try:
        handler.filter(record)
    finally:
        correlation_id_var.reset(token)

    assert "[cid-de-prueba]" in handler.format(record)
