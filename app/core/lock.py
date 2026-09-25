"""Puerto abstracto de lock distribuido por clave."""

from abc import ABC, abstractmethod


class Lock(ABC):
    """Exclusión mutua entre instancias del servicio."""

    @abstractmethod
    async def acquire(self, key: str) -> str:
        """Toma el lock de la clave y devuelve el token para liberarlo.

        Lanza LockTimeoutError si otro lo tiene y no se libera a tiempo, y
        LockUnavailableError si el lock no responde.
        """

    @abstractmethod
    async def release(self, key: str, token: str) -> None:
        """Libera el lock solo si sigue siendo del dueño de ese token.

        No lanza: si el lock no responde, vence solo por su expiración.
        """
