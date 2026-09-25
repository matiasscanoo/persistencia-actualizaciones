"""Suite de contrato de Repository: la misma para memoria y MongoDB (LSP)."""

import pytest

from app.core.exceptions import DuplicateChecksumError
from app.models.documento_pdf import DocumentoPdf

pytestmark = pytest.mark.asyncio

CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


@pytest.fixture(
    params=[
        "repositorio_en_memoria",
        pytest.param("repositorio_mongo", marks=pytest.mark.integration),
    ],
    ids=["memoria", "mongo"],
)
def repositorio(request):
    return request.getfixturevalue(request.param)


def documento(**cambios) -> DocumentoPdf:
    datos = {
        "nombre": "contrato.pdf",
        "checksum": CHECKSUM,
        "texto": "Contenido extraído del PDF",
        "tamano_bytes": 245760,
        "paginas": 3,
    }
    return DocumentoPdf(**{**datos, **cambios})


@pytest.mark.parametrize("paginas", [3, None])
async def test_get_by_id_devuelve_el_documento_guardado(repositorio, paginas):
    guardado = await repositorio.add(documento(paginas=paginas))

    assert await repositorio.get_by_id(guardado.id) == guardado


async def test_get_by_id_inexistente_devuelve_none(repositorio):
    assert await repositorio.get_by_id("no-existe") is None


async def test_add_con_checksum_repetido_lanza_duplicate_checksum(repositorio):
    await repositorio.add(documento())

    with pytest.raises(DuplicateChecksumError) as error:
        await repositorio.add(documento(nombre="otro.pdf"))

    assert error.value.checksum == CHECKSUM


async def test_update_reemplaza_el_documento_guardado(repositorio):
    guardado = await repositorio.add(documento())
    guardado.nombre = "nuevo.pdf"
    guardado.update_timestamp()

    await repositorio.update(guardado)

    assert await repositorio.get_by_id(guardado.id) == guardado


async def test_modificar_lo_leido_no_persiste_sin_update(repositorio):
    guardado = await repositorio.add(documento())
    leido = await repositorio.get_by_id(guardado.id)

    leido.nombre = "cambiado-sin-update.pdf"

    assert (await repositorio.get_by_id(guardado.id)).nombre == "contrato.pdf"


async def test_delete_devuelve_el_documento_borrado(repositorio):
    guardado = await repositorio.add(documento())

    assert await repositorio.delete(guardado.id) == guardado
    assert await repositorio.get_by_id(guardado.id) is None


async def test_delete_inexistente_devuelve_none(repositorio):
    assert await repositorio.delete("no-existe") is None


async def test_delete_libera_el_checksum(repositorio):
    guardado = await repositorio.add(documento())
    await repositorio.delete(guardado.id)

    nuevo = await repositorio.add(documento())

    assert nuevo.checksum == CHECKSUM
