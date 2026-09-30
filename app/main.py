"""Composición de la aplicación: routers, middleware, handlers de error y DI."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.controllers.documento_controller import router as documento_router
from app.controllers.health_controller import router as health_router
from app.core.exceptions import (
    DatabaseError,
    DuplicateChecksumError,
    LockTimeoutError,
    ResourceNotFoundError,
)
from app.core.logging_context import CorrelationIdFilter, correlation_id_var
from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

# Un correlation ID demasiado largo o con caracteres no imprimibles podría
# inyectar contenido arbitrario en los logs (A17).
MAX_LARGO_CORRELATION_ID = 128


def _configurar_logging() -> None:
    """Cada línea de log incluye el correlation_id del request en curso."""
    handler = logging.StreamHandler()
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s"
        )
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])


_configurar_logging()

app = FastAPI(title="persistencia-actualizaciones")

app.include_router(health_router)
app.include_router(documento_router)


def _es_ascii_imprimible(valor: str) -> bool:
    return all(0x20 <= ord(caracter) <= 0x7E for caracter in valor)


def _resolver_correlation_id(recibido: str | None) -> str:
    """Propaga el header si es válido; si no, genera un UUID v4 (A17)."""
    if (
        recibido
        and len(recibido) <= MAX_LARGO_CORRELATION_ID
        and _es_ascii_imprimible(recibido)
    ):
        return recibido
    return str(uuid4())


@app.middleware("http")
async def middleware_correlation_id(request: Request, call_next):
    """Lee o genera el correlation ID; lo expone al logging y a los handlers."""
    correlation_id = _resolver_correlation_id(request.headers.get("X-Correlation-ID"))
    request.state.correlation_id = correlation_id
    token = correlation_id_var.set(correlation_id)
    try:
        response = await call_next(request)
    finally:
        correlation_id_var.reset(token)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


def _error_response(
    request: Request, status_code: int, code: str, message: str, details: dict
) -> JSONResponse:
    error = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            correlation_id=request.state.correlation_id,
        )
    )
    # Se fija también acá (no solo en el middleware): el handler de Exception
    # corre en ServerErrorMiddleware, fuera de nuestro middleware de request.
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(),
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


def _campo(loc: tuple) -> str:
    """Ruta del campo sin el prefijo de ubicación de FastAPI (A14)."""
    if len(loc) <= 1:
        return "body"
    return ".".join(str(parte) for parte in loc[1:])


@app.exception_handler(RequestValidationError)
async def manejar_error_de_validacion(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errores = [{"field": _campo(e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return _error_response(
        request, 400, "VALIDATION_ERROR", "Error de validación", {"errors": errores}
    )


@app.exception_handler(ResourceNotFoundError)
async def manejar_recurso_no_encontrado(
    request: Request, exc: ResourceNotFoundError
) -> JSONResponse:
    return _error_response(request, 404, exc.error_code, exc.message, {"id": exc.id})


@app.exception_handler(DuplicateChecksumError)
async def manejar_checksum_duplicado(
    request: Request, exc: DuplicateChecksumError
) -> JSONResponse:
    return _error_response(
        request, 409, exc.error_code, exc.message, {"checksum": exc.checksum}
    )


@app.exception_handler(DatabaseError)
async def manejar_error_de_base_de_datos(
    request: Request, exc: DatabaseError
) -> JSONResponse:
    logger.warning("Base de datos no disponible")
    return _error_response(request, 503, exc.error_code, exc.message, {})


@app.exception_handler(LockTimeoutError)
async def manejar_lock_timeout(request: Request, exc: LockTimeoutError) -> JSONResponse:
    return _error_response(
        request, 503, exc.error_code, exc.message, {"reason": exc.reason}
    )


@app.exception_handler(Exception)
async def manejar_error_no_controlado(request: Request, exc: Exception) -> JSONResponse:
    """No filtra la traza al cliente; el detalle queda solo en el log."""
    logger.error("Error no controlado", exc_info=exc)
    return _error_response(
        request, 500, "INTERNAL_ERROR", "Error interno del servidor", {}
    )
