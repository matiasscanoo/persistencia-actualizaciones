from app.core.dependencia import Dependencia


class DependenciaFija(Dependencia):
    """Servicio de apoyo con disponibilidad fija, para probar /health sin MongoDB ni
    Redis."""

    def __init__(self, disponible: bool) -> None:
        self._disponible = disponible

    async def disponible(self) -> bool:
        return self._disponible
