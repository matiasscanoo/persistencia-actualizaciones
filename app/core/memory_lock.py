"""Implementación en memoria de Lock, doble de prueba sin red."""

from uuid import uuid4

from app.core.exceptions import LockTimeoutError
from app.core.lock import Lock


class InMemoryLock(Lock):
    """Locks en un diccionario clave → token.

    Una clave tomada falla enseguida con LockTimeoutError: en memoria nadie la
    libera mientras se espera. Los reintentos hasta el timeout son del adaptador
    Redis.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    @property
    def claves_tomadas(self) -> set[str]:
        return set(self._tokens)

    async def acquire(self, key: str) -> str:
        if key in self._tokens:
            raise LockTimeoutError(key)
        token = str(uuid4())
        self._tokens[key] = token
        return token

    async def release(self, key: str, token: str) -> None:
        if self._tokens.get(key) == token:
            del self._tokens[key]
