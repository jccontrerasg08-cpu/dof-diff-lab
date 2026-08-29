# DOF Intelligence Lab

**DOF Intelligence Lab** is a daily, traceable monitor and searchable corpus for Mexico's Diario Oficial de la Federación (DOF). It prefers structured SIDOF open-data responses, falls back to the official DOF HTML index, preserves deterministic hashes and provenance, and can optionally use Tavily to discover official URLs when site structure changes.

> **No afiliación y uso responsable.** Este proyecto no está afiliado, patrocinado ni respaldado por el DOF ni por una autoridad pública. La **fuente primaria** siempre es la publicación oficial enlazada en `dof.gob.mx` o `sidof.segob.gob.mx`. El corpus, las etiquetas, hashes, diffs y cualquier salida de IA son derivados técnicos: no certifican autenticidad jurídica, no determinan vigencia ni efectos regulatorios y **no sustituye** la consulta de la fuente oficial ni asesoría profesional.

## Architecture

The scheduled path is intentionally hybrid rather than “LLM first”:

1. `SIDOF` structured JSON is queried first for daily notes and editions.
2. If SIDOF is empty or unavailable, the monitor checks the official `dof.gob.mx` index as a fallback/cross-check.
3. Canonical records are normalized, tagged with deterministic rules and hashed.
4. A local SQLite FTS5 corpus can be rebuilt from all normalized records and searched without any external service.
5. Tavily is optional discovery-only infrastructure. It is restricted to official DOF/SIDOF domains and never becomes a source of legal truth.

A legitimate day without a publication is `no_edition` and exits successfully. Network failures, unexpected HTTP/MIME responses and malformed pages remain hard failures so “source broke” is never silently converted to “nothing happened”.

## Versioned artifacts

| Artifact | Contents | Purpose |
|---|---|---|
| `data/normalized/YYYY-MM-DD/<edition>.json` | note code, official URL, title, issuer, deterministic tags and record hash | reproducible corpus input |
| `data/manifests/YYYY-MM-DD/<edition>.json` | source id, timestamp, parser/schema version and normalized hash | provenance and diagnostics |
| `data/diffs/YYYY-MM-DD[-edition].md` | additions, removals and metadata changes | human review |
| `data/state/latest.json` | latest source, date, status and editions | operational state |
| `site/index.html` | current source-linked summary | public inspection |
| `.tmp/dof-corpus.sqlite3` | generated SQLite/FTS corpus | local search; not committed |

## Daily sync

```text
python3 -m dof_diff_lab.intelligence sync --date 2026-08-29 --root .
```

The command uses SIDOF first and the legacy official DOF index as fallback. It requires no API key.

The lower-level deterministic HTML monitor remains available for diagnostics:

```text
python3 -m dof_diff_lab.monitor --date 2026-08-29 --root .
```

## Build and search the corpus

```text
python3 -m dof_diff_lab.intelligence build --root . --database .tmp/dof-corpus.sqlite3
python3 -m dof_diff_lab.intelligence search "comercio exterior" --database .tmp/dof-corpus.sqlite3
python3 -m dof_diff_lab.intelligence search "SECRETARIA DE ECONOMIA" --database .tmp/dof-corpus.sqlite3 --limit 20
```

Search results retain the publication date, edition, note code, issuer and official canonical URL so they can be cited or passed into a downstream RAG/LLM layer without losing provenance.

## Optional Tavily discovery

Set `TAVILY_API_KEY` only if you want web discovery. It is not required by scheduled runs.

```text
export TAVILY_API_KEY="..."
python3 -m dof_diff_lab.intelligence discover "DOF comercio exterior cambios recientes"
```

Discovery requests include only the allowlisted official hosts `dof.gob.mx`, `www.dof.gob.mx` and `sidof.segob.gob.mx`. Returned URLs are validated again before being exposed. Tavily results are marked conceptually as `discovery_only`; the project still requires an official source adapter to ingest authoritative content.

## Deterministic labels

The built-in labels remain explainable rule matches, not model probabilities or legal conclusions. Examples include document type (`acuerdo`, `decreto`, `resolucion`, `norma`), textual signals (`possible_modification`, `possible_repeal`, `contains_deadline`) and discovery topics (`fiscal`, `trade`, `labor`, `health`, `environment`). Every stored tag contains rule id/version and evidence.

## GitHub automation

The scheduled workflow runs daily at **16:17 UTC** and also supports manual ISO-date recovery. The capture job performs the hybrid sync, builds a SQLite corpus artifact, uploads verified outputs, and only then allows the publisher to commit changed `data/` and `site/` files. The corpus database stays an Actions artifact rather than a binary tracked in git.

## Development checks

```text
python3 tests/check_cli.py
python3 tests/check_monitor.py
python3 tests/check_monitor_workflow.py
python3 tests/check_public_readiness.py
python3 tests/check_sources.py
python3 tests/check_corpus.py
python3 tests/check_discovery.py
python3 tests/check_intelligence.py
```

No test needs a network connection or secret. See [`docs/superpowers/specs/2026-08-29-dof-intelligence-corpus-design.md`](docs/superpowers/specs/2026-08-29-dof-intelligence-corpus-design.md) for the current design and [`SECURITY.md`](SECURITY.md) for responsible reporting.

## Sources and provenance

SIDOF publishes open-data WebServices for diarios, documentos, indicadores and notas. The current adapter targets the public unauthenticated SIDOF JSON surface under `https://sidof.segob.gob.mx/dof/sidof/` and retains `dof.gob.mx` as an independent official fallback. When citing a result, use the official canonical URL, publication date, note code and repository manifest/commit where applicable.

## License

Project code is Apache-2.0. DOF content remains subject to its official terms; this repository does not attempt to relicense official publications or replace the gazette.
