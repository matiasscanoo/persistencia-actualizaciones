"""Implementación en memoria de Cache, doble de prueba sin red."""

from fnmatch import fnmatchcase

from app.core.cache import Cache


class InMemoryCache(Cache):
    """Claves cacheadas en un set; los patrones se resuelven como en Redis."""

    def __init__(self) -> None:
        self.claves: set[str] = set()

    async def invalidate(self, keys: list[str]) -> None:
        self.claves = {
            clave
            for clave in self.claves
            if not any(fnmatchcase(clave, patron) for patron in keys)
        }
