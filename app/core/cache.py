"""Puerto abstracto de caché: este servicio solo invalida, nunca escribe."""

from abc import ABC, abstractmethod


class Cache(ABC):
    """Caché compartida con persistencia-consultas."""

    @abstractmethod
    async def invalidate(self, keys: list[str]) -> None:
        """Borra las claves; las que terminan en `*` son patrones.

        Lanza CacheUnavailableError si la caché no responde.
        """
