"""Tests de serialización de los schemas de response y error (contrato, 3 y 4)."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.documento_pdf import DocumentoPdf
from app.schemas.documento import DocumentoResponse
from app.schemas.error import ErrorDetail, ErrorResponse

ID = "8f6f7c3e-12d5-4f57-9c6c-123456789abc"
CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
CREADO = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
MODIFICADO = datetime(2026, 9, 14, 18, 30, 5, 123000, tzinfo=timezone.utc)


def documento(**cambios) -> DocumentoPdf:
    datos = {
        "id": ID,
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
        "created_at": CREADO,
        "updated_at": MODIFICADO,
    }
    return DocumentoPdf(**{**datos, **cambios})


def serializar(entidad: DocumentoPdf) -> dict:
    return DocumentoResponse.model_validate(entidad).model_dump(mode="json")


def test_response_serializa_el_documento_como_el_contrato():
    assert serializar(documento()) == {
        "id": ID,
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
        "created_at": "2026-09-14T18:00:00.000Z",
        "updated_at": "2026-09-14T18:30:05.123Z",
    }


def test_response_respeta_el_orden_de_claves_del_contrato():
    assert list(serializar(documento())) == [
        "id",
        "nombre",
        "checksum",
        "texto",
        "tamano_bytes",
        "paginas",
        "created_at",
        "updated_at",
    ]


def test_response_incluye_paginas_null():
    assert serializar(documento(paginas=None))["paginas"] is None


def test_response_expresa_las_fechas_en_utc_aunque_vengan_con_otro_offset():
    menos_tres = timezone(timedelta(hours=-3))
    creado = datetime(2026, 9, 14, 15, 0, tzinfo=menos_tres)

    assert serializar(documento(created_at=creado))["created_at"] == (
        "2026-09-14T18:00:00.000Z"
    )


def test_error_response_serializa_el_formato_comun():
    error = ErrorResponse(
        error=ErrorDetail(
            code="DUPLICATE_CHECKSUM",
            message="Ya existe un documento con ese checksum",
            details={"checksum": CHECKSUM},
            correlation_id="abc-123",
        )
    )

    assert error.model_dump(mode="json") == {
        "error": {
            "code": "DUPLICATE_CHECKSUM",
            "message": "Ya existe un documento con ese checksum",
            "details": {"checksum": CHECKSUM},
            "correlation_id": "abc-123",
        }
    }


def test_error_detail_sin_details_serializa_objeto_vacio():
    detalle = ErrorDetail(
        code="INTERNAL_ERROR", message="Error interno", correlation_id="abc-123"
    )

    assert detalle.model_dump(mode="json")["details"] == {}


def test_error_detail_rechaza_codigos_fuera_del_contrato():
    with pytest.raises(ValidationError):
        ErrorDetail(code="METHOD_NOT_ALLOWED", message="x", correlation_id="abc")
