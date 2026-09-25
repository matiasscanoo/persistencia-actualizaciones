"""Clientes de MongoDB (Motor) y Redis; main.py los crea al arrancar."""

from motor.motor_asyncio import AsyncIOMotorClient

# Sin respuesta de Mongo en este tiempo, la operación falla con 503 en vez de
# esperar los 30 s por defecto del driver.
MONGO_TIMEOUT_MS = 5000


def crear_cliente_mongo(uri: str) -> AsyncIOMotorClient:
    """Cliente Motor que devuelve las fechas como datetime UTC con zona horaria."""
    return AsyncIOMotorClient(
        uri, tz_aware=True, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS
    )
