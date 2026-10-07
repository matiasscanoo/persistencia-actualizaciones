"""Correlation ID disponible para el logging durante todo el request (contrato 6.5).

El middleware de main.py fija la variable al entrar; cualquier logger de la
app, incluidos los warnings de fail-open en documento_service.py, la expone
en sus líneas sin recibirla como parámetro explícito. El formato y el handler
salen de logging.json (contrato 1.2.0).
"""

import json
import logging.config
from contextvars import ContextVar
from logging import Filter, LogRecord
from pathlib import Path

# logging.json vive en la raíz del repo y se copia a la imagen.
LOGGING_JSON = Path(__file__).resolve().parents[2] / "logging.json"

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationIdFilter(Filter):
    """Agrega `record.correlation_id` para que el formatter lo incluya."""

    def filter(self, record: LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


def configurar_logs(nivel: str = "INFO") -> None:
    """Carga logging.json (handler a stdout, 12-Factor XI) con el nivel dado.
    LOG_LEVEL se aplica en el lifespan, cuando Settings ya está validado."""
    logging.config.dictConfig(json.loads(LOGGING_JSON.read_text(encoding="utf-8")))
    logging.getLogger().setLevel(nivel)
