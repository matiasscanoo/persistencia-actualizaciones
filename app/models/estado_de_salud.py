from dataclasses import dataclass


@dataclass(frozen=True)
class EstadoDeSalud:
    ok: bool
    dependencias: dict[str, str]
