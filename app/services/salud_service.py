import asyncio

from app.core.dependencia import Dependencia
from app.models.estado_de_salud import EstadoDeSalud


def _estado(disponible: bool) -> str:
    return "ok" if disponible else "caido"


class SaludService:
    """Contrato 1.2.0: el servicio está fuera de servicio solo si MongoDB no responde.
    Redis caído se informa pero no cuenta: se escribe sin lock y sin invalidar
    (fail-open), y el índice único de checksum sigue garantizando la unicidad."""

    def __init__(self, mongodb: Dependencia, redis: Dependencia) -> None:
        self._mongodb = mongodb
        self._redis = redis

    async def estado(self) -> EstadoDeSalud:
        mongodb, redis = await asyncio.gather(
            self._mongodb.disponible(), self._redis.disponible()
        )
        return EstadoDeSalud(
            ok=mongodb,
            dependencias={"mongodb": _estado(mongodb), "redis": _estado(redis)},
        )
