"""Implementación en memoria de Repository, doble de prueba sin red."""

from app.core.repository import Repository, T


class InMemoryRepository(Repository[T]):
    """Repositorio en un diccionario indexado por id."""

    def __init__(self) -> None:
        self._entidades: dict[str, T] = {}

    async def add(self, entity: T) -> T:
        self._entidades[entity.id] = entity
        return entity
