"""Puerto abstracto de persistencia: solo los métodos que el service invoca."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.models.base_model import BaseEntity

T = TypeVar("T", bound=BaseEntity)


class Repository(ABC, Generic[T]):
    """Persistencia de entidades del dominio."""

    @abstractmethod
    async def add(self, entity: T) -> T:
        """Guarda una entidad nueva y la devuelve."""
