"""Proveedores de los servicios para Depends(); no conocen Mongo ni Redis.

El cableado concreto (MongoRepository, RedisCache, RedisLock y las
dependencias de /health) vive en el lifespan de main.py, que arma las
instancias y las guarda en app.state.
"""

from fastapi import Request

from app.services.documento_service import DocumentoService
from app.services.salud_service import SaludService


def get_documento_service(request: Request) -> DocumentoService:
    """Devuelve la instancia armada en el lifespan de main.py."""
    return request.app.state.documento_service


def get_salud_service(request: Request) -> SaludService:
    """Devuelve la instancia armada en el lifespan de main.py."""
    return request.app.state.salud_service
