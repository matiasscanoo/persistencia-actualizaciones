"""GET /health: liveness. No consulta MongoDB ni Redis (contrato, A16)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
