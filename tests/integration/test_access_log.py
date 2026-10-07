"""Registro de acceso desde el middleware, con el correlation_id del request.

Reemplaza al access log de uvicorn (desactivado en la imagen), que se emite
fuera del contexto del request y no lleva el correlation_id (contrato 6.5).
"""

import logging

from app.core.logging_context import CorrelationIdFilter


def test_cada_request_se_registra_con_su_correlation_id(cliente_http, caplog) -> None:
    caplog.set_level(logging.INFO)
    caplog.handler.addFilter(CorrelationIdFilter())

    cliente_http.get("/health", headers={"X-Correlation-ID": "cid-acceso"})

    accesos = [
        r
        for r in caplog.records
        if "method=GET path=/health status=200" in r.getMessage()
    ]
    assert accesos
    assert accesos[0].correlation_id == "cid-acceso"
