"""Entidad de dominio DocumentoPdf (Python puro, sin Pydantic)."""

from dataclasses import dataclass

from app.models.base_model import BaseEntity


@dataclass(kw_only=True)
class DocumentoPdf(BaseEntity):
    """Documento PDF persistido: metadatos y texto extraído, sin el binario."""

    nombre: str
    checksum: str
    texto: str
    tamano_bytes: int
    paginas: int | None
