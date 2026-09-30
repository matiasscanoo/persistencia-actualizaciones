"""Proveedor de DocumentoService para Depends(); no conoce Mongo ni Redis.

El cableado concreto (MongoRepository, RedisCache, RedisLock) vive en el
lifespan de main.py, que arma la instancia y la guarda en app.state.
"""

from fastapi import Request

from app.services.documento_service import DocumentoService


def get_documento_service(request: Request) -> DocumentoService:
    """Devuelve la instancia armada en el lifespan de main.py."""
    return request.app.state.documento_service
