"""Rutas HTTP de documentos PDF (CAPA 1): sin reglas de negocio ni BD concreta."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_documento_service
from app.schemas.documento import DocumentoCreateRequest, DocumentoResponse
from app.services.documento_service import DocumentoService

router = APIRouter()


@router.post("/pdf", response_model=DocumentoResponse, status_code=201)
async def crear_documento(
    body: DocumentoCreateRequest,
    servicio: DocumentoService = Depends(get_documento_service),
) -> DocumentoResponse:
    documento = await servicio.crear(
        nombre=body.nombre,
        checksum=body.checksum,
        texto=body.texto,
        tamano_bytes=body.tamano_bytes,
        paginas=body.paginas,
    )
    return DocumentoResponse.model_validate(documento)
