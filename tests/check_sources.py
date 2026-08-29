from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dof_diff_lab.sources import OFFICIAL_HOSTS, SOURCE_REGISTRY, normalize_sidof_payload, sidof_notes_url


def main() -> None:
    assert SOURCE_REGISTRY["sidof"]["authority"] == "primary"
    assert SOURCE_REGISTRY["dof_index"]["authority"] == "primary"
    assert SOURCE_REGISTRY["tavily"]["authority"] == "discovery_only"
    assert OFFICIAL_HOSTS == {"dof.gob.mx", "www.dof.gob.mx", "sidof.segob.gob.mx"}
    assert sidof_notes_url(date(2026, 8, 29)).endswith("/notas/29-08-2026")

    empty = normalize_sidof_payload({"Notas": []}, date(2026, 8, 29))
    assert empty == []

    payload = {
        "Notas": [
            {
                "codNota": 5796484,
                "titulo": "Acuerdo por el que se modifica el Código Fiscal de la Federación.",
                "organismo": "SECRETARIA DE HACIENDA Y CREDITO PUBLICO",
                "codEdicion": "MAT",
            }
        ]
    }
    notes = normalize_sidof_payload(payload, date(2026, 8, 18))
    assert len(notes) == 1
    assert notes[0]["code"] == "5796484"
    assert notes[0]["edition"] == "matutina"
    assert notes[0]["canonical_url"].startswith("https://sidof.segob.gob.mx/")
    assert notes[0]["source_id"] == "sidof"


if __name__ == "__main__":
    main()
