# DOF Intelligence Lab

**DOF Intelligence Lab** is a traceable monitor and searchable corpus for Mexico's Diario Oficial de la Federación (DOF). It prefers structured SIDOF open data, falls back to the official DOF HTML index, preserves deterministic provenance, and can optionally use Tavily only to discover official URLs.

> **No afiliación y uso responsable.** Este proyecto no está afiliado, patrocinado ni respaldado por el DOF ni por una autoridad pública. La fuente primaria siempre es la publicación oficial enlazada en `dof.gob.mx` o `sidof.segob.gob.mx`. Los catálogos, etiquetas, hashes y diffs son derivados técnicos: no determinan vigencia ni efectos jurídicos y no sustituyen la consulta oficial ni asesoría profesional.

## How it works

1. Query SIDOF daily JSON and normalize matutina, vespertina and extraordinaria notes.
2. Preserve official metadata, human-facing URLs, API provenance, availability flags and record hashes.
3. If SIDOF is unavailable or empty, cross-check the official DOF HTML index.
4. Write deterministic normalized JSON, manifests, diffs and a static inspection page.
5. Rebuild a local SQLite FTS5 corpus for lexical search.
6. Optionally use Tavily Search for official-domain URL discovery. Tavily never becomes the publication source of truth.

The runtime is Python-standard-library only. There is no browser automation, OCR stack, vector database or mandatory external SDK.

## Commands

```text
python3 -m dof_diff_lab sync --date 2026-08-29 --root .
python3 -m dof_diff_lab build --root . --database .tmp/dof-corpus.sqlite3
python3 -m dof_diff_lab search "comercio exterior" --database .tmp/dof-corpus.sqlite3
```

For optional discovery:

```text
export TAVILY_API_KEY="..."
python3 -m dof_diff_lab discover "DOF comercio exterior cambios recientes"
```

The lower-level fallback parser is also available for diagnostics:

```text
python3 -m dof_diff_lab.monitor --date 2026-08-29 --root .
```

## Artifacts

| Artifact | Purpose |
|---|---|
| `data/normalized/YYYY-MM-DD/<edition>.json` | canonical records for comparison and corpus ingestion |
| `data/manifests/YYYY-MM-DD/<edition>.json` | provenance, parser/schema information and hashes |
| `data/diffs/YYYY-MM-DD[-edition].md` | human-readable deterministic changes |
| `data/state/latest.json` | latest operational state |
| `site/index.html` | source-linked static inspection view |
| `.tmp/dof-corpus.sqlite3` | generated search database; artifact only, not committed |

A legitimate day with no publication is `no_edition`. Unexpected HTTP/MIME responses and malformed weekday pages remain errors so source failures are not confused with absence of news.

## Automation

GitHub Actions checks the Mexican publication date at **16:17, 22:17 and 03:17 UTC**. The 03:17 UTC run resolves the date in `America/Mexico_City`, avoiding an accidental next-day query while giving vespertina/extraordinaria editions another capture window.

The workflow syncs official sources, builds the corpus artifact, uploads verified derivatives, commits only changed `data/` and `site/` outputs, and deploys the static site. Actions are pinned by commit SHA and jobs use minimum required permissions.

## Development checks

```text
python3 tests/check_entrypoint.py
python3 tests/check_monitor.py
python3 tests/check_monitor_workflow.py
python3 tests/check_public_readiness.py
python3 tests/check_sources.py
python3 tests/check_corpus.py
python3 tests/check_discovery.py
python3 tests/check_intelligence.py
```

Tests are network-free and need no secrets. See [`docs/monitor-architecture.md`](docs/monitor-architecture.md) for the current design and [`SECURITY.md`](SECURITY.md) for responsible reporting.

## Design boundaries

The current system deliberately stays mostly deterministic. SQLite FTS5 is sufficient for the existing normalized corpus and exact legal terminology. A vector/LLM layer should only be added if evaluation demonstrates retrieval value that lexical and metadata search cannot provide. Tavily remains discovery-only, and AI-generated legal conclusions are outside this repository's trust boundary.

## License

Project code is Apache-2.0. DOF content remains subject to its official terms; this repository does not attempt to relicense official publications or replace the gazette.
