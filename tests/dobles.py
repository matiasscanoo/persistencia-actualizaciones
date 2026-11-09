from app.core.health_check import HealthCheck


class HealthCheckFijo(HealthCheck):
    """Servicio de apoyo con disponibilidad fija, para probar /health sin MongoDB ni
    Redis."""

    def __init__(self, disponible: bool) -> None:
        self._disponible = disponible

    async def disponible(self) -> bool:
        return self._disponible
