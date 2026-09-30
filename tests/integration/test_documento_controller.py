"""Tests HTTP de POST /pdf con dobles en memoria (contrato, secciones 2.1 y 3.1)."""

from uuid import UUID

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def test_post_pdf_crea_documento_y_devuelve_201(cliente_http) -> None:
    body = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
    }

    respuesta = cliente_http.post("/pdf", json=body)

    assert respuesta.status_code == 201
    documento = respuesta.json()
    assert documento["nombre"] == "contrato.pdf"
    assert documento["checksum"] == CHECKSUM
    assert documento["texto"] == "Contenido extraído del PDF"
    assert documento["tamano_bytes"] == 245760
    assert documento["paginas"] == 3
    assert documento["created_at"] == documento["updated_at"]
    assert UUID(documento["id"])


def test_patch_pdf_actualiza_nombre_y_devuelve_200(cliente_http) -> None:
    body = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
    }
    creado = cliente_http.post("/pdf", json=body).json()

    respuesta = cliente_http.patch(
        f"/pdf/{creado['id']}", json={"nombre": "contrato-renombrado.pdf"}
    )

    assert respuesta.status_code == 200
    documento = respuesta.json()
    assert documento["id"] == creado["id"]
    assert documento["nombre"] == "contrato-renombrado.pdf"
    assert documento["checksum"] == creado["checksum"]
    assert documento["created_at"] == creado["created_at"]


def test_delete_pdf_elimina_documento_y_devuelve_204(cliente_http) -> None:
    body = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
    }
    creado = cliente_http.post("/pdf", json=body).json()

    respuesta = cliente_http.delete(f"/pdf/{creado['id']}")

    assert respuesta.status_code == 204
    assert respuesta.content == b""
