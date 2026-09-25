"""Excepciones de dominio; cada una lleva su código de error del contrato."""


class AppError(Exception):
    """Base de las excepciones de dominio."""

    def __init__(self, message: str, error_code: str) -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class DuplicateChecksumError(AppError):
    """Ya existe un documento con ese checksum."""

    def __init__(self, checksum: str) -> None:
        self.checksum = checksum
        super().__init__(
            "Ya existe un documento con ese checksum", "DUPLICATE_CHECKSUM"
        )


class ResourceNotFoundError(AppError):
    """No existe un documento con ese id."""

    def __init__(self, id: str) -> None:
        self.id = id
        super().__init__("No existe un documento con ese id", "RESOURCE_NOT_FOUND")
