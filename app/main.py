"""Composición de la aplicación: routers, middleware, handlers de error y DI."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.controllers.documento_controller import router as documento_router
from app.controllers.health_controller import router as health_router
from app.core.config import Settings
from app.core.database import crear_cliente_mongo, crear_cliente_redis
from app.core.exceptions import (
    DatabaseError,
    DuplicateChecksumError,
    LockTimeoutError,
    ResourceNotFoundError,
)
from app.core.logging_context import configurar_logs, correlation_id_var
from app.core.mongo_repository import MongoRepository
from app.core.redis_cache import RedisCache
from app.core.redis_lock import RedisLock
from app.schemas.error import ErrorDetail, ErrorResponse
from app.services.documento_service import DocumentoService

logger = logging.getLogger(__name__)

# Un correlation ID demasiado largo o con caracteres no imprimibles podría
# inyectar contenido arbitrario en los logs (A17).
MAX_LARGO_CORRELATION_ID = 128


configurar_logs()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Arma DocumentoService con adaptadores reales; cierra las conexiones al apagar."""
    settings = Settings()
    logging.getLogger().setLevel(settings.log_level)
    mongo_client = crear_cliente_mongo(settings.mongo_uri)
    redis_client = crear_cliente_redis(settings.redis_url)
    coleccion = mongo_client[settings.mongo_database][settings.mongo_collection]
    repository = MongoRepository(coleccion)
    await repository.crear_indices()
    cache = RedisCache(redis_client)
    lock = RedisLock(redis_client, settings.lock_timeout_seconds)
    app.state.documento_service = DocumentoService(repository, cache, lock)
    logger.info("servicio iniciado")
    try:
        yield
    finally:
        # uvicorn llega acá ante SIGTERM, después de cerrar el puerto y terminar
        # las escrituras en curso (12-Factor IX).
        logger.info("apagado iniciado")
        mongo_client.close()
        await redis_client.aclose()
        logger.info("apagado completo")


app = FastAPI(title="persistencia-actualizaciones", lifespan=lifespan)

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
    inicio = time.perf_counter()
    try:
        response = await call_next(request)
        # Reemplaza al access log de uvicorn, que no lleva el correlation_id.
        logger.info(
            "method=%s path=%s status=%s duracion_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - inicio) * 1000,
        )
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


def _campo(error: dict) -> str:
    """Ruta del campo sin el prefijo de ubicación de FastAPI (A14).

    Si el body entero es inválido (JSON mal formado), FastAPI reporta
    `loc=("body", <posición>)`: el campo sigue siendo "body", no la posición.
    """
    if error["type"] == "json_invalid":
        return "body"
    loc = error["loc"]
    if len(loc) <= 1:
        return "body"
    return ".".join(str(parte) for parte in loc[1:])


@app.exception_handler(RequestValidationError)
async def manejar_error_de_validacion(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errores = [{"field": _campo(e), "message": e["msg"]} for e in exc.errors()]
    return _error_response(
        request, 400, "VALIDATION_ERROR", "Error de validación", {"errors": errores}
    )


@app.exception_handler(StarletteHTTPException)
async def manejar_ruta_o_metodo_no_definidos(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Rutas o métodos fuera del contrato, en el formato común de error (A18).

    Starlette solo levanta este HTTPException con 404 (ruta inexistente) o 405
    (método no permitido en una ruta que sí existe); no hay un tercer caso.
    """
    if exc.status_code == 405:
        return _error_response(
            request,
            405,
            "VALIDATION_ERROR",
            "Método no permitido",
            {"reason": "method_not_allowed"},
        )
    return _error_response(
        request, 404, "RESOURCE_NOT_FOUND", "Recurso no encontrado", {}
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
