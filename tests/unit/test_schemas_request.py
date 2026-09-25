"""Tests de validación de los schemas de request (contrato, secciones 2.1 y 2.2)."""

import pytest
from pydantic import ValidationError

from app.schemas.documento import DocumentoCreateRequest, DocumentoUpdateRequest

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def body_create(**cambios) -> dict:
    body = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
    }
    return {**body, **cambios}


def test_create_acepta_un_body_valido():
    request = DocumentoCreateRequest.model_validate(body_create())

    assert request.nombre == "contrato.pdf"
    assert request.checksum == CHECKSUM
    assert request.texto == "Contenido extraído del PDF"
    assert request.tamano_bytes == 245760
    assert request.paginas == 3


def test_create_sin_paginas_la_deja_en_none():
    body = body_create()
    del body["paginas"]

    assert DocumentoCreateRequest.model_validate(body).paginas is None


@pytest.mark.parametrize(
    "cambios",
    [
        {"texto": ""},
        {"paginas": 0},
        {"paginas": None},
        {"tamano_bytes": 1},
        {"nombre": "n" * 255},
        {"nombre": "  contrato.pdf  "},
    ],
    ids=[
        "texto-vacio",
        "cero-paginas",
        "paginas-null",
        "un-byte",
        "nombre-255",
        "nombre-con-espacios-alrededor",
    ],
)
def test_create_acepta_casos_limite_validos(cambios):
    request = DocumentoCreateRequest.model_validate(body_create(**cambios))

    for campo, valor in cambios.items():
        assert getattr(request, campo) == valor


@pytest.mark.parametrize(
    "cambios",
    [
        {"nombre": ""},
        {"nombre": "   "},
        {"nombre": "n" * 256},
        {"checksum": CHECKSUM.upper()},
        {"checksum": "a7f5f35426b927411fc9231b56382173"},
        {"checksum": CHECKSUM[:-1] + "g"},
        {"tamano_bytes": 0},
        {"tamano_bytes": -1},
        {"paginas": -1},
        {"tamano_bytes": "245760"},
        {"tamano_bytes": True},
        {"tamano_bytes": 245760.0},
        {"paginas": "3"},
        {"nombre": 123},
    ],
    ids=[
        "nombre-vacio",
        "nombre-solo-espacios",
        "nombre-256",
        "checksum-mayusculas",
        "checksum-32-hex",
        "checksum-no-hex",
        "tamano-cero",
        "tamano-negativo",
        "paginas-negativas",
        "tamano-string",
        "tamano-bool",
        "tamano-float",
        "paginas-string",
        "nombre-numero",
    ],
)
def test_create_rechaza_valores_invalidos(cambios):
    with pytest.raises(ValidationError):
        DocumentoCreateRequest.model_validate(body_create(**cambios))


@pytest.mark.parametrize("campo", ["nombre", "checksum", "texto", "tamano_bytes"])
def test_create_rechaza_si_falta_un_campo_obligatorio(campo):
    body = body_create()
    del body[campo]

    with pytest.raises(ValidationError):
        DocumentoCreateRequest.model_validate(body)


@pytest.mark.parametrize(
    "extra",
    [
        {"id": "8f6f7c3e-12d5-4f57-9c6c-123456789abc"},
        {"created_at": "2026-09-14T18:00:00.000Z"},
        {"autor": "alguien"},
    ],
    ids=["id", "created_at", "campo-desconocido"],
)
def test_create_rechaza_campos_extra(extra):
    with pytest.raises(ValidationError):
        DocumentoCreateRequest.model_validate(body_create(**extra))


def test_update_acepta_solo_nombre():
    request = DocumentoUpdateRequest.model_validate({"nombre": "nuevo.pdf"})

    assert request.nombre == "nuevo.pdf"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"nombre": ""},
        {"nombre": "   "},
        {"nombre": "n" * 256},
        {"nombre": "nuevo.pdf", "checksum": CHECKSUM},
        {"nombre": "nuevo.pdf", "texto": "otro"},
    ],
    ids=[
        "vacio",
        "nombre-vacio",
        "nombre-solo-espacios",
        "nombre-256",
        "con-checksum",
        "con-texto",
    ],
)
def test_update_rechaza_bodies_invalidos(body):
    with pytest.raises(ValidationError):
        DocumentoUpdateRequest.model_validate(body)
