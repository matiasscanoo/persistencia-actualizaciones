"""Formato común de error del contrato (sección 4)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

CodigoError = Literal[
    "VALIDATION_ERROR",
    "RESOURCE_NOT_FOUND",
    "DUPLICATE_CHECKSUM",
    "DATABASE_ERROR",
    "DEPENDENCY_UNAVAILABLE",
    "INTERNAL_ERROR",
]


class ErrorDetail(BaseModel):
    """Contenido de `error`; `details` siempre presente, aunque sea `{}`."""

    code: CodigoError
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str


class ErrorResponse(BaseModel):
    """Cuerpo de toda respuesta de error: `{"error": {...}}`."""

    error: ErrorDetail
