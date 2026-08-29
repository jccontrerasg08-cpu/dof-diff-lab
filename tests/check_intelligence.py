from datetime import date
from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dof_diff_lab.intelligence import sync_date
from dof_diff_lab.monitor import ParseError, SourceResponse

HTML = b"""
<html><body>
<p>Fecha: 18/08/2026 - Edicion Matutina</p>
<p>PRIMERA</p><p>PODER EJECUTIVO</p><p>SECRETARIA DE ECONOMIA</p>
<a href='https://dof.gob.mx/nota_detalle.php?codigo=5796484&fecha=18/08/2026'>Acuerdo de comercio exterior.</a>
</body></html>
"""

GENERIC_SHELL = b"<html><body><p>Diario Oficial de la Federacion</p></body></html>"


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = sync_date(
            date(2026, 8, 18),
            root,
            sidof_fetch=lambda _date: [{
                "code": "5796484",
                "title": "Acuerdo de comercio exterior.",
                "canonical_url": "https://sidof.segob.gob.mx/dof/sidof/notas/nota/5796484",
                "publication_date": "2026-08-18",
                "edition": "matutina",
                "issuer_primary": None,
                "issuer_secondary": "SECRETARIA DE ECONOMIA",
                "source_id": "sidof",
            }],
        )
        assert result["source_id"] == "sidof"
        path = root / "data" / "normalized" / "2026-08-18" / "matutina.json"
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["notes"][0]["code"] == "5796484"
        assert payload["notes"][0]["tags"]

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = sync_date(
            date(2026, 8, 18),
            root,
            sidof_fetch=lambda _date: [],
            dof_fetch=lambda _url: SourceResponse(200, "text/html", HTML),
        )
        assert result["source_id"] == "dof_index"
        assert result["status"] == "changed"

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = sync_date(
            date(2026, 8, 29),
            root,
            sidof_fetch=lambda _date: [],
            dof_fetch=lambda _url: SourceResponse(200, "text/html", GENERIC_SHELL),
        )
        assert result["status"] == "no_edition"
        assert result["source_id"] == "sidof+dof_index"
        assert (root / "data" / "normalized" / "2026-08-29" / "matutina.json").is_file()

    with tempfile.TemporaryDirectory() as directory:
        try:
            sync_date(
                date(2026, 8, 31),
                Path(directory),
                sidof_fetch=lambda _date: [],
                dof_fetch=lambda _url: SourceResponse(200, "text/html", GENERIC_SHELL),
            )
        except ParseError:
            pass
        else:
            raise AssertionError("An empty SIDOF response must not hide a malformed weekday DOF response")


if __name__ == "__main__":
    main()
