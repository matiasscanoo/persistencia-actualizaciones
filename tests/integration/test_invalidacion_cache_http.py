"""Invalidación de caché observada a nivel HTTP (contrato, sección 7.1)."""

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

BODY_VALIDO = {
    "nombre": "contrato.pdf",
    "checksum": CHECKSUM,
    "texto": "Contenido extraído del PDF",
    "tamano_bytes": 245760,
    "paginas": 3,
}


def test_post_pdf_invalida_checksum_y_listados_en_la_cache(cliente_http) -> None:
    cliente_http.cache.claves = {f"pdf:checksum:{CHECKSUM}", "pdf:list:pagina=1"}

    respuesta = cliente_http.post("/pdf", json=BODY_VALIDO)

    assert respuesta.status_code == 201
    assert cliente_http.cache.claves == set()


def test_patch_pdf_invalida_id_checksum_y_listados_en_la_cache(cliente_http) -> None:
    creado = cliente_http.post("/pdf", json=BODY_VALIDO).json()
    cliente_http.cache.claves = {
        f"pdf:id:{creado['id']}",
        f"pdf:checksum:{CHECKSUM}",
        "pdf:list:pagina=1",
    }

    respuesta = cliente_http.patch(
        f"/pdf/{creado['id']}", json={"nombre": "renombrado.pdf"}
    )

    assert respuesta.status_code == 200
    assert cliente_http.cache.claves == set()


def test_delete_pdf_invalida_id_checksum_y_listados_en_la_cache(cliente_http) -> None:
    creado = cliente_http.post("/pdf", json=BODY_VALIDO).json()
    cliente_http.cache.claves = {
        f"pdf:id:{creado['id']}",
        f"pdf:checksum:{CHECKSUM}",
        "pdf:list:pagina=1",
    }

    respuesta = cliente_http.delete(f"/pdf/{creado['id']}")

    assert respuesta.status_code == 204
    assert cliente_http.cache.claves == set()


def test_post_pdf_con_checksum_duplicado_no_invalida_la_cache(cliente_http) -> None:
    cliente_http.post("/pdf", json=BODY_VALIDO)
    cliente_http.cache.claves = {"pdf:list:pagina=1"}

    respuesta = cliente_http.post("/pdf", json={**BODY_VALIDO, "nombre": "otro.pdf"})

    assert respuesta.status_code == 409
    assert cliente_http.cache.claves == {"pdf:list:pagina=1"}
