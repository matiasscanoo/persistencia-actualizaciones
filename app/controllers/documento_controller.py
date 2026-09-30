"""Rutas HTTP de documentos PDF (CAPA 1): sin reglas de negocio ni BD concreta."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from app.core.dependencies import get_documento_service
from app.schemas.documento import (
    DocumentoCreateRequest,
    DocumentoResponse,
    DocumentoUpdateRequest,
)
from app.services.documento_service import DocumentoService

router = APIRouter()

# La ruta se llama {id} como en el contrato; el alias hace que un id inválido
# se reporte con field "id" (A14) sin sombrear el builtin id().
IdDocumento = Annotated[UUID, Path(alias="id")]


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


@router.patch("/pdf/{id}", response_model=DocumentoResponse, status_code=200)
async def actualizar_documento(
    documento_id: IdDocumento,
    body: DocumentoUpdateRequest,
    servicio: DocumentoService = Depends(get_documento_service),
) -> DocumentoResponse:
    documento = await servicio.actualizar_nombre(str(documento_id), nombre=body.nombre)
    return DocumentoResponse.model_validate(documento)


@router.delete("/pdf/{id}", status_code=204)
async def eliminar_documento(
    documento_id: IdDocumento,
    servicio: DocumentoService = Depends(get_documento_service),
) -> None:
    await servicio.eliminar(str(documento_id))
