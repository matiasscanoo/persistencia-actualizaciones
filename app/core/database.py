"""Clientes de MongoDB (Motor) y Redis; main.py los crea al arrancar."""

from motor.motor_asyncio import AsyncIOMotorClient
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff

# Sin respuesta de Mongo en este tiempo, la operación falla con 503 en vez de
# esperar los 30 s por defecto del driver.
MONGO_TIMEOUT_MS = 5000


def crear_cliente_mongo(uri: str) -> AsyncIOMotorClient:
    """Cliente Motor que devuelve las fechas como datetime UTC con zona horaria."""
    return AsyncIOMotorClient(
        uri, tz_aware=True, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS
    )


# Con Redis caído, redis-py con su configuración por defecto tarda ~26 s en
# rendirse porque reintenta con backoff. Con fail-open, cada escritura esperaría
# ese tiempo: por eso el cliente no reintenta y usa timeouts cortos.
REDIS_TIMEOUT_S = 1.0

# Errores que significan "Redis no responde"; el resto son bugs y se propagan.
ERRORES_DE_CONEXION_REDIS = (
    redis_exceptions.ConnectionError,
    redis_exceptions.TimeoutError,
)


def crear_cliente_redis(url: str, timeout_s: float = REDIS_TIMEOUT_S) -> Redis:
    """Cliente Redis que falla rápido si Redis no responde."""
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=timeout_s,
        socket_timeout=timeout_s,
        retry=Retry(NoBackoff(), 0),
    )
