from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    dependencias: dict[str, Literal["ok", "caido"]]
