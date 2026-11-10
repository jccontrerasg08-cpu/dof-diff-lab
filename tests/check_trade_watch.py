"""No-network acceptance tests for candidate-only, title-based trade triage."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dof_diff_lab.trade_watch import (
    _official_url,
    parse_iso_date,
    scan_trade_candidates,
    title_signals,
)


def _sample(root: Path) -> Path:
    folder = root / "data" / "normalized" / "2026-11-10"
    folder.mkdir(parents=True)
    records = [
        {
            "code": "101", "title": "Decreto por el que se modifica la TIGIE.",
            "title_available": True,
            "canonical_url": "https://sidof.segob.gob.mx/notas/101",
            "record_sha256": "a" * 64,
            "source_id": "sidof",
        },
        {
            "code": "102", "title": "Reglas Generales de Comercio Exterior para 2026.",
            "canonical_url": "https://dof.gob.mx/nota_detalle.php?codigo=102",
            "source_id": "dof_index",
        },
        {
            "code": "103", "title": "Reporte de importacion de energia para el mercado.",
            "canonical_url": "https://sidof.segob.gob.mx/notas/103",
        },
        {
            "code": "104", "title": "Nota DOF 104",
            "title_available": False,
            "canonical_url": "https://sidof.segob.gob.mx/notas/104",
        },
        {
            "code": "105", "title": "Decreto arancelario de prueba",
            "canonical_url": "https://evil.example/notas/105",
        },
        {
            "code": "106", "title": "Acuerdo por el que se reforman los aranceles y NICO.",
            "canonical_url": "https://www.dof.gob.mx/nota_detalle.php?codigo=106",
        },
    ]
    path = folder / "matutina.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "source": {
                    "publication_date": "2026-11-10",
                    "edition": "matutina",
                    "source_id": "sidof",
                },
                "notes": records,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def main() -> None:
    assert title_signals("Decreto que modifica la LIGIE")[0]["family"] == "tariff"
    assert title_signals("Acuerdo de Regulaciones y Restricciones No Arancelarias")[0]["family"] == "trade_regulation"
    assert title_signals("RGCE para el próximo año")[0]["family"] == "trade_regulation"
    assert title_signals("Tratado de comercio exterior") == []
    assert title_signals("Informe de importación de manzanas") == []
    assert not _official_url("https://sidof.segob.gob.mx.evil.invalid/notas/1")
    assert not _official_url("http://sidof.segob.gob.mx/notas/1")
    assert not _official_url("https://evil.example/notas/1")
    assert _official_url("https://sidof.segob.gob.mx/notas/1")
    for bad in ("2026-11-1", "2026-13-10", "10/11/2026"):
        try:
            parse_iso_date(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        assert scan_trade_candidates(root / "data" / "normalized")["status"] == "no_local_catalogs"
        path = _sample(root)
        results = scan_trade_candidates(root / "data" / "normalized")
        assert results == scan_trade_candidates(root / "data" / "normalized")
        assert results["status"] == "scan_complete"
        assert results["coverage"] == {
            "local_catalogs_scanned": 1,
            "notes_with_official_url_and_title": 4,
            "notes_missing_title": 1,
            "notes_rejected_nonofficial_url": 1,
            "candidate_total": 3,
            "results_truncated": False,
        }
        candidates = results["candidates"]
        assert [item["code"] for item in candidates] == ["101", "102", "106"]
        assert [item["priority"] for item in candidates] == [
            "priority_review", "review", "priority_review"
        ]
        assert candidates[0]["record_sha256"] == "a" * 64
        assert candidates[0]["canonical_url"].startswith("https://sidof.segob.gob.mx")
        assert all(item["review_status"] == "unverified_title_match" for item in candidates)

        limited = scan_trade_candidates(root / "data" / "normalized", limit=1)
        assert limited["coverage"]["results_truncated"] is True
        assert len(limited["candidates"]) == 1
        assert scan_trade_candidates(root / "data" / "normalized", start=date(2026, 11, 11))["status"] == "no_local_catalogs"
        assert scan_trade_candidates(root / "data" / "normalized", end=date(2026, 11, 9))["candidates"] == []
        for kwargs in ({"limit": 0}, {"limit": True}, {"start": date(2026, 11, 11), "end": date(2026, 11, 9)}):
            try:
                scan_trade_candidates(root / "data" / "normalized", **kwargs)
            except ValueError:
                pass
            else:
                raise AssertionError(kwargs)

        cmd = subprocess.run(
            [
                sys.executable, "-m", "dof_diff_lab", "triage",
                "--root", str(root), "--start", "2026-11-10", "--limit", "2",
            ],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        assert cmd.returncode == 0, cmd.stderr
        payload = json.loads(cmd.stdout)
        assert len(payload["candidates"]) == 2
        assert payload["coverage"]["candidate_total"] == 3
        assert payload["disclaimer"].startswith("Title matches")

        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["source"]["publication_date"] = "2026-11-09"
        path.write_text(json.dumps(stored), encoding="utf-8")
        try:
            scan_trade_candidates(root / "data" / "normalized")
        except ValueError as err:
            assert "date" in str(err)
        else:
            raise AssertionError("Malformed catalog must fail closed")


if __name__ == "__main__":
    main()
