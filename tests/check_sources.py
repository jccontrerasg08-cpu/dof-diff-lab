from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dof_diff_lab.sources import OFFICIAL_HOSTS, fetch_json, normalize_sidof_payload, sidof_notes_url


def test_fetch_json_retries_transient_io() -> None:
    class Response:
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"response":"OK","NotasMatutinas":[]}'

    attempts: list[int] = []

    def opener(_request: object, timeout: int) -> Response:
        attempts.append(timeout)
        if len(attempts) == 1:
            raise TimeoutError("temporary SIDOF timeout")
        return Response()

    payload = fetch_json(
        "https://sidof.segob.gob.mx/dof/sidof/notas/29-08-2026",
        attempts=2,
        opener=opener,
        sleeper=lambda _seconds: None,
    )
    assert isinstance(payload, dict)
    assert attempts == [30, 30]


def main() -> None:
    test_fetch_json_retries_transient_io()
    assert OFFICIAL_HOSTS == {"dof.gob.mx", "www.dof.gob.mx", "sidof.segob.gob.mx"}
    assert sidof_notes_url(date(2026, 8, 29)).endswith("/notas/29-08-2026")

    empty = normalize_sidof_payload(
        {"messageCode": 200, "response": "OK", "NotasMatutinas": [], "NotasVespertinas": [], "NotasExtraordinarias": []},
        date(2026, 8, 29),
    )
    assert empty == []

    payload = {
        "messageCode": 200,
        "response": "OK",
        "NotasMatutinas": [
            {
                "codNota": 5796484,
                "titulo": "Acuerdo por el que se modifica el Código Fiscal de la Federación.",
                "codSeccion": "PRIMERA",
                "codDiario": 300001,
                "pagina": 2,
                "paginaHasta": 5,
                "existeHtml": "S",
                "existeDoc": "S",
                "existeImagen": "S",
                "nombreCodOrgaUno": "PODER EJECUTIVO",
                "codOrgaDos": "SECRETARIA DE HACIENDA Y CREDITO PUBLICO",
            }
        ],
        "NotasVespertinas": [
            {
                "codNota": 5796999,
                "titulo": "Aviso vespertino de prueba.",
                "codSeccion": "UNICA",
                "existeHtml": "N",
                "existeImagen": "S",
                "nombreCodOrgaUno": "PODER EJECUTIVO",
                "codOrgaDos": "SECRETARIA DE ECONOMIA",
            }
        ],
        "NotasExtraordinarias": [
            {
                "codNota": 5797000,
                "codSeccion": "UNICA",
                "existeHtml": "N",
                "existeImagen": "N",
                "nombreCodOrgaUno": "PODER EJECUTIVO",
                "codOrgaDos": "SECRETARIA DE GOBERNACION",
            }
        ],
    }
    notes = normalize_sidof_payload(payload, date(2026, 8, 18))
    assert len(notes) == 3
    by_code = {note["code"]: note for note in notes}
    assert by_code["5796484"]["edition"] == "matutina"
    assert by_code["5796999"]["edition"] == "vespertina"
    assert by_code["5797000"]["edition"] == "extraordinaria"
    assert by_code["5796484"]["issuer_primary"] == "PODER EJECUTIVO"
    assert by_code["5796484"]["issuer_secondary"] == "SECRETARIA DE HACIENDA Y CREDITO PUBLICO"
    assert by_code["5796484"]["section"] == "PRIMERA"
    assert by_code["5797000"]["title"] == "Nota DOF 5797000"
    assert by_code["5797000"]["title_available"] is False
    assert by_code["5796484"]["canonical_url"] == "https://sidof.segob.gob.mx/notas/5796484"
    assert by_code["5796999"]["canonical_url"] == "https://sidof.segob.gob.mx/notas/imagenes/5796999"
    assert by_code["5796484"]["source_api_url"].endswith("/notas/nota/5796484")
    assert by_code["5796484"]["has_html"] is True
    assert by_code["5796484"]["has_document"] is True
    assert by_code["5796484"]["has_image"] is True
    assert by_code["5796484"]["page_start"] == 2
    assert by_code["5796484"]["page_end"] == 5
    assert by_code["5796484"]["journal_code"] == "300001"
    assert all(note["source_id"] == "sidof" for note in notes)


if __name__ == "__main__":
    main()