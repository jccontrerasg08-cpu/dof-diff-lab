# DOF Intelligence Lab architecture

## Scope

DOF Intelligence Lab is a small, traceable ingestion and search system for Mexico's Diario Oficial de la Federación. It does not determine legal effect. Official DOF/SIDOF publications remain the source of truth.

## Runtime flow

```text
SIDOF daily JSON (primary structured source)
        |
        | notes present
        v
normalize editions + provenance
        |
        +--> deterministic title tags
        +--> SHA-256 record hashes
        +--> versioned JSON / manifests / diffs
        +--> static inspection page
        |
        v
SQLite FTS5 corpus (generated artifact)

SIDOF unavailable or empty
        |
        v
DOF HTML index (independent official fallback/cross-check)
```

Tavily is outside the ingestion trust path. The optional `discover` command uses Tavily Search only to locate candidate URLs and restricts both requests and returned results to official DOF/SIDOF hosts. Discovery output is never treated as an authoritative publication without an official-source adapter.

## Modules

| Module | Responsibility |
|---|---|
| `sources.py` | Official source registry, SIDOF URLs, daily response normalization and public provenance fields. |
| `monitor.py` | Deterministic DOF HTML parser, fallback capture, tags, hashes, manifests, diffs and static rendering. |
| `intelligence.py` | Orchestration CLI: `sync`, `build`, `search`, `discover`; SIDOF-first policy and fallback rules. |
| `corpus.py` | Rebuildable SQLite FTS5 index over normalized records. |
| `discovery.py` | Optional Tavily URL discovery with an official-host allowlist. |
| `__main__.py` | Thin package entrypoint forwarding to the intelligence CLI. |

The project intentionally has no Python runtime dependencies outside the standard library. SQLite FTS5 is supplied by CPython's SQLite build. Tavily is called through `urllib`, so no SDK is required.

## Source policy

`sidof.segob.gob.mx` and `dof.gob.mx` are primary official sources. SIDOF is preferred because its daily service exposes matutina, vespertina and extraordinaria groups. The DOF HTML index remains valuable as an independent fallback and for cross-checking no-publication states.

Each SIDOF record preserves a human-facing canonical URL plus its machine-facing API URL when available. Availability flags (`has_html`, `has_document`, `has_image`), page range and journal code are retained when supplied by SIDOF. Missing titles are represented explicitly with `title_available=false`; synthetic fallback labels are not passed through title-classification rules.

## Editions and schedule

GitHub Actions checks the publication day in three windows: 16:17, 22:17 and 03:17 UTC. The publication date is resolved in `America/Mexico_City`, so the after-midnight UTC check still targets the intended Mexican publication date.

Repeated runs are idempotent. Existing normalized data for an edition is loaded before writing and compared by stable note identity plus record hash. A legitimate absence is `no_edition`; malformed weekday responses and source failures remain errors.

## Stored artifacts

- `data/normalized/YYYY-MM-DD/<edition>.json`: canonical note records.
- `data/manifests/YYYY-MM-DD/<edition>.json`: provenance and parser/schema metadata.
- `data/diffs/YYYY-MM-DD[-edition].md`: deterministic changes for human review.
- `data/state/latest.json`: latest successful operational state.
- `site/index.html`: generated static inspection view.
- `.tmp/dof-corpus.sqlite3`: generated FTS database, kept as an Actions artifact and never committed.

Raw DOF/SIDOF responses are not committed. Hashes and source metadata are retained where the capture path exposes them.

## Deliberate non-features

There is no vector database, autonomous legal agent, LLM classification, Selenium/browser scraper, OCR pipeline, or Tavily crawler in the production path. Those would add cost and failure modes without being necessary for the current corpus size and retrieval needs. Semantic/vector retrieval can be added later behind the existing normalized corpus only if evaluation shows a measurable benefit over FTS5.

## Verification contract

The CI suite is network-free and covers package entrypoint behavior, DOF parsing and retry semantics, no-publication handling, SIDOF edition normalization, provenance retention, corpus search, Tavily host restrictions, workflow permissions/scheduling, and public-readiness safeguards. GitHub Actions are pinned by commit SHA.
