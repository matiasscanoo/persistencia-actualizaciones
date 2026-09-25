"""DTOs HTTP de documentos PDF (capa 1), distintos de la entidad DocumentoPdf."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer


def _no_en_blanco(valor: str) -> str:
    if not valor.strip():
        raise ValueError("no puede estar vacío ni tener solo espacios")
    return valor


Nombre = Annotated[str, Field(max_length=255), AfterValidator(_no_en_blanco)]


def _iso_utc_con_milisegundos(fecha: datetime) -> str:
    """ISO-8601 en UTC con sufijo Z y siempre 3 decimales (A15)."""
    iso = fecha.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    return iso.replace("+00:00", "Z")


FechaUtc = Annotated[
    datetime,
    PlainSerializer(_iso_utc_con_milisegundos, return_type=str, when_used="json"),
]


class _Request(BaseModel):
    """Campos extra rechazados (A5) y tipos estrictos, sin conversiones (A13)."""

    model_config = ConfigDict(extra="forbid", strict=True)


class DocumentoCreateRequest(_Request):
    """Body de POST /pdf."""

    nombre: Nombre
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    texto: str
    tamano_bytes: int = Field(ge=1)
    paginas: int | None = Field(default=None, ge=0)


class DocumentoUpdateRequest(_Request):
    """Body de PATCH /pdf/{id}: solo el nombre es editable."""

    nombre: Nombre


class DocumentoResponse(BaseModel):
    """Documento completo de POST y PATCH, construido desde la entidad."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    nombre: str
    checksum: str
    texto: str
    tamano_bytes: int
    paginas: int | None
    created_at: FechaUtc
    updated_at: FechaUtc
