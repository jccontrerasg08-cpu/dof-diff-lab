from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dof_diff_lab.corpus import build_corpus, search_corpus


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "data" / "normalized" / "2026-08-18"
        source.mkdir(parents=True)
        (source / "matutina.json").write_text(json.dumps({
            "source": {"publication_date": "2026-08-18", "edition": "matutina"},
            "notes": [{
                "code": "5796484",
                "title": "Acuerdo que modifica la Regla 3.1.8 de comercio exterior y aranceles",
                "canonical_url": "https://dof.gob.mx/nota_detalle.php?codigo=5796484",
                "issuer_primary": "PODER EJECUTIVO",
                "issuer_secondary": "SECRETARIA DE ECONOMIA",
                "tags": [
                    {"name": "document_type", "value": "acuerdo"},
                    {"name": "topic", "value": "trade"}
                ]
            }]
        }), encoding="utf-8")
        db = root / "corpus.sqlite3"
        count = build_corpus(root / "data" / "normalized", db)
        assert count == 1
        results = search_corpus(db, "comercio exterior", limit=5)
        assert len(results) == 1
        assert results[0]["code"] == "5796484"
        assert results[0]["issuer"] == "SECRETARIA DE ECONOMIA"
        assert results[0]["publication_date"] == "2026-08-18"
        assert results[0]["canonical_url"].startswith("https://dof.gob.mx/")
        punctuated = search_corpus(db, "Regla 3.1.8: comercio exterior", limit=5)
        assert len(punctuated) == 1
        assert punctuated[0]["code"] == "5796484"
        assert search_corpus(db, "salud", limit=5) == []
        assert search_corpus(db, "!!!", limit=5) == []


if __name__ == "__main__":
    main()
