"""Correlation ID disponible para el logging durante todo el request (contrato 6.5).

El middleware de main.py fija la variable al entrar; cualquier logger de la
app, incluidos los warnings de fail-open en documento_service.py, la expone
en sus líneas sin recibirla como parámetro explícito.
"""

from contextvars import ContextVar
from logging import Filter, LogRecord

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationIdFilter(Filter):
    """Agrega `record.correlation_id` para que el formatter lo incluya."""

    def filter(self, record: LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True
