from abc import ABC, abstractmethod


class Dependencia(ABC):
    """Servicio de apoyo que GET /health consulta (contrato 1.2.0)."""

    @abstractmethod
    async def disponible(self) -> bool: ...
