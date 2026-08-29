from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dof_diff_lab.monitor as monitor
from dof_diff_lab.monitor import ParseError, SourceResponse, run_monitor


BASE_INDEX = """
<!doctype html>
<html><body>
<p>Fecha: 18/08/2026 - Edición Matutina</p>
<p>PRIMERA</p>
<p>PODER EJECUTIVO</p>
<p>SECRETARIA DE HACIENDA Y CREDITO PUBLICO</p>
<a href="https://dof.gob.mx/nota_detalle.php?codigo=5796484&amp;fecha=18/08/2026">
  Acuerdo por el que se modifica el Código Fiscal de la Federación.
</a>
<p>ORGANISMOS AUTONOMOS</p>
<p>BANCO DE MEXICO</p>
<a href="https://dof.gob.mx/nota_detalle.php?codigo=5796505&amp;fecha=18/08/2026">
  Tipo de cambio para solventar obligaciones denominadas en moneda extranjera pagaderas en la República Mexicana.
</a>
</body></html>
"""

MODIFIED_INDEX = BASE_INDEX.replace(
    "Acuerdo por el que se modifica el Código Fiscal de la Federación.",
    "Acuerdo por el que se modifica y adiciona el Código Fiscal de la Federación.",
)

EMPTY_INDEX = """
<!doctype html>
<html><body>
<p>Fecha: 19/08/2026 - Edición Matutina</p>
<p>Sin publicaciones para la edición consultada.</p>
</body></html>
"""

WEEKEND_INDEX = """
<!doctype html>
<html><head><title>Diario Oficial de la Federación</title></head>
<body>
<div id="contenido">No existen publicaciones para la fecha seleccionada.</div>
</body></html>
"""

MALFORMED_INDEX = """
<!doctype html>
<html><body><p>Portal temporal sin índice ni mensaje de no publicación.</p></body></html>
"""


def response(body: str) -> SourceResponse:
    return SourceResponse(
        status=200,
        content_type="text/html; charset=utf-8",
        body=body.encode("utf-8"),
    )


def test_fetch_retries_timeout() -> None:
    class Headers:
        def get_content_type(self) -> str:
            return "text/html"

    class Response:
        status = 200
        headers = Headers()

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"<html></html>"

    attempts: list[str] = []

    def opener(_request: object, timeout: int) -> Response:
        attempts.append(str(timeout))
        if len(attempts) == 1:
            raise TimeoutError("simulated timeout")
        return Response()

    result = monitor.fetch_official_index(
        "https://dof.gob.mx/example",
        attempts=2,
        opener=opener,
        sleeper=lambda _seconds: None,
    )
    assert result.status == 200
    assert result.body == b"<html></html>"
    assert attempts == ["30", "30"]


def test_weekend_page_is_no_edition() -> None:
    assert monitor.parse_official_index(response(WEEKEND_INDEX).body, "https://dof.gob.mx/example") == []


def test_malformed_page_still_fails() -> None:
    try:
        monitor.parse_official_index(response(MALFORMED_INDEX).body, "https://dof.gob.mx/example")
    except ParseError:
        return
    raise AssertionError("A malformed portal response must not be treated as no_edition")


def main() -> None:
    test_fetch_retries_timeout()
    test_weekend_page_is_no_edition()
    test_malformed_page_still_fails()
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        publication_date = date(2026, 8, 18)

        first = run_monitor(
            publication_date=publication_date,
            root=workspace,
            fetch=lambda _url: response(BASE_INDEX),
        )
        assert first.status == "changed"
        assert first.note_count == 2
        assert first.index_url == "https://dof.gob.mx/index_113.php?year=2026&month=08&day=18"

        normalized_path = workspace / "data" / "normalized" / "2026-08-18" / "matutina.json"
        manifest_path = workspace / "data" / "manifests" / "2026-08-18" / "matutina.json"
        diff_path = workspace / "data" / "diffs" / "2026-08-18.md"
        state_path = workspace / "data" / "state" / "latest.json"
        site_path = workspace / "site" / "index.html"
        for path in (normalized_path, manifest_path, diff_path, state_path, site_path):
            assert path.is_file(), path
        assert not (workspace / "data" / "raw").exists()

        catalog = json.loads(normalized_path.read_text(encoding="utf-8"))
        assert catalog["schema_version"] == "1.0"
        assert catalog["source"]["publication_date"] == "2026-08-18"
        assert catalog["source"]["edition"] == "matutina"
        assert [note["code"] for note in catalog["notes"]] == ["5796484", "5796505"]

        fiscal_note = catalog["notes"][0]
        assert fiscal_note["issuer_primary"] == "PODER EJECUTIVO"
        assert fiscal_note["issuer_secondary"] == "SECRETARIA DE HACIENDA Y CREDITO PUBLICO"
        assert fiscal_note["record_sha256"]
        tags = {(tag["name"], tag["value"]) for tag in fiscal_note["tags"]}
        assert ("document_type", "acuerdo") in tags
        assert ("signal", "possible_modification") in tags
        assert ("topic", "fiscal") in tags
        assert all(tag["evidence"] and tag["rule_id"] and tag["rule_version"] for tag in fiscal_note["tags"])

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["status"] == "changed"
        assert manifest["source"]["http_status"] == 200
        assert manifest["source"]["raw_sha256"]
        assert manifest["normalized_sha256"]
        assert manifest["insights"]["by_document_type"]["acuerdo"] == 1
        assert "## Altas (2)" in diff_path.read_text(encoding="utf-8")
        site_html = site_path.read_text(encoding="utf-8")
        assert "Monitor diario del DOF" in site_html
        assert "No afiliación" in site_html
        assert "Coincidencias de reglas" in site_html
        assert "Regla:" in site_html
        assert "5796484" in site_html
        assert "https://dof.gob.mx/nota_detalle.php?codigo=5796484" in site_html

        second = run_monitor(
            publication_date=publication_date,
            root=workspace,
            fetch=lambda _url: response(BASE_INDEX),
        )
        assert second.status == "no_change"
        assert "Sin cambios" in diff_path.read_text(encoding="utf-8")

        third = run_monitor(
            publication_date=publication_date,
            root=workspace,
            fetch=lambda _url: response(MODIFIED_INDEX),
        )
        assert third.status == "changed"
        assert "## Modificaciones (1)" in diff_path.read_text(encoding="utf-8")
        assert "adiciona" in diff_path.read_text(encoding="utf-8")
        assert not (workspace / "data" / "raw").exists()

        empty = run_monitor(
            publication_date=date(2026, 8, 19),
            root=workspace,
            fetch=lambda _url: response(EMPTY_INDEX),
        )
        assert empty.status == "no_edition"
        assert empty.note_count == 0
        empty_manifest = json.loads(
            (workspace / "data" / "manifests" / "2026-08-19" / "matutina.json").read_text(encoding="utf-8")
        )
        assert empty_manifest["status"] == "no_edition"
        assert "Sin publicaciones" in (workspace / "data" / "diffs" / "2026-08-19.md").read_text(encoding="utf-8")

        weekend = run_monitor(
            publication_date=date(2026, 8, 29),
            root=workspace,
            fetch=lambda _url: response(WEEKEND_INDEX),
        )
        assert weekend.status == "no_edition"
        assert weekend.note_count == 0


if __name__ == "__main__":
    main()
