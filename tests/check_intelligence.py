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
                "canonical_url": "https://sidof.segob.gob.mx/notas/5796484",
                "source_api_url": "https://sidof.segob.gob.mx/dof/sidof/notas/nota/5796484",
                "publication_date": "2026-08-18",
                "edition": "matutina",
                "section": "PRIMERA",
                "issuer_primary": "PODER EJECUTIVO",
                "issuer_secondary": "SECRETARIA DE ECONOMIA",
                "source_id": "sidof",
                "title_available": True,
                "has_html": True,
                "has_document": True,
                "has_image": True,
                "page_start": 2,
                "page_end": 5,
                "journal_code": "300001",
            }],
        )
        assert result["source_id"] == "sidof"
        path = root / "data" / "normalized" / "2026-08-18" / "matutina.json"
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        note = payload["notes"][0]
        assert note["code"] == "5796484"
        assert note["tags"]
        assert note["canonical_url"] == "https://sidof.segob.gob.mx/notas/5796484"
        assert note["source_api_url"].endswith("/notas/nota/5796484")
        assert note["title_available"] is True
        assert note["has_html"] is True
        assert note["has_document"] is True
        assert note["has_image"] is True
        assert note["page_start"] == 2
        assert note["page_end"] == 5
        assert note["journal_code"] == "300001"

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
            date(2026, 8, 18),
            root,
            sidof_fetch=lambda _date: (_ for _ in ()).throw(OSError("temporary outage")),
            dof_fetch=lambda _url: SourceResponse(200, "text/html", HTML),
        )
        assert result["source_id"] == "dof_index"
        assert "temporary outage" in str(result["sidof_error"])

    dof_called = False

    def unexpected_dof(_url: str) -> SourceResponse:
        nonlocal dof_called
        dof_called = True
        return SourceResponse(200, "text/html", HTML)

    try:
        sync_date(
            date(2026, 8, 18),
            Path("."),
            sidof_fetch=lambda _date: (_ for _ in ()).throw(RuntimeError("programming bug")),
            dof_fetch=unexpected_dof,
        )
    except RuntimeError as error:
        assert str(error) == "programming bug"
    else:
        raise AssertionError("Programming errors from SIDOF normalization must propagate")
    assert dof_called is False

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