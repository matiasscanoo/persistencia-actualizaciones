"""DTOs HTTP de documentos PDF (capa 1), distintos de la entidad DocumentoPdf."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _no_en_blanco(valor: str) -> str:
    if not valor.strip():
        raise ValueError("no puede estar vacío ni tener solo espacios")
    return valor


Nombre = Annotated[str, Field(max_length=255), AfterValidator(_no_en_blanco)]


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
