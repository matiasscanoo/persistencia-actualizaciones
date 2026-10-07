"""GET /health: informa MongoDB y Redis; 503 solo si MongoDB no responde
(contrato 1.2.0, reemplaza el liveness sin dependencias de A16)."""

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import get_salud_service
from app.schemas.health import HealthResponse
from app.services.salud_service import SaludService

router = APIRouter()


@router.get(
    "/health",
    responses={503: {"model": HealthResponse, "description": "MongoDB no responde."}},
)
async def health(
    response: Response, servicio: SaludService = Depends(get_salud_service)
) -> HealthResponse:
    estado = await servicio.estado()
    if not estado.ok:
        response.status_code = 503
    return HealthResponse(
        status="ok" if estado.ok else "error", dependencias=estado.dependencias
    )
