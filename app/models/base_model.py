"""Entidad base del dominio: id UUID y timestamps UTC."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def ahora_utc() -> datetime:
    """Hora actual en UTC truncada a milisegundos, la precisión de MongoDB (A15)."""
    ahora = datetime.now(timezone.utc)
    return ahora.replace(microsecond=ahora.microsecond // 1000 * 1000)


@dataclass(kw_only=True)
class BaseEntity:
    """Entidad con id UUID v4 y fechas de creación y modificación en UTC.

    Si no se pasan, se generan; `updated_at` arranca igual a `created_at`.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=ahora_utc)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.updated_at is None:
            self.updated_at = self.created_at
