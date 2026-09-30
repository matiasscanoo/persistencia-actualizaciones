"""Test unitario de CorrelationIdFilter, sin pasar por el pipeline de logging.

logging.basicConfig() en main.py no hace nada bajo pytest porque el plugin de
logging de pytest ya configuró el root logger antes; por eso este test ejercita
el filtro directamente en vez de depender de esa configuración.
"""

import logging

from app.core.logging_context import CorrelationIdFilter, correlation_id_var


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
