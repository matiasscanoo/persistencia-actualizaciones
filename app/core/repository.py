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

    @abstractmethod
    async def get_by_id(self, entity_id: str) -> T | None:
        """Devuelve la entidad con ese id, o None si no existe."""

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Reemplaza la entidad guardada con el mismo id y la devuelve."""
