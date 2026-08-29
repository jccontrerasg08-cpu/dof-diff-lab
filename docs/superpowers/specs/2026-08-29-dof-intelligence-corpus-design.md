# DOF Intelligence Corpus Design

## Goal

Evolve the existing deterministic DOF monitor into a resilient, source-aware ingestion and search system without weakening provenance. The official DOF/SIDOF remains authoritative. AI/web discovery may help locate or enrich official material but never decides whether a legal publication exists or what its legal effect is.

## Problems being solved

1. Scheduled runs currently fail on valid no-publication days because an empty/unrecognized DOF index is treated as a parser error.
2. The monitor is tied to one HTML index pattern and one hard-coded `matutina` edition.
3. The repository stores useful normalized metadata but lacks a searchable historical corpus.
4. There is no source registry, fallback strategy, or optional discovery layer for locating changing official surfaces.

## Architecture

### 1. Authoritative source adapters

`SIDOF` is the preferred structured source when available. It exposes date and note endpoints under `https://sidof.segob.gob.mx/dof/sidof/`. The legacy `dof.gob.mx` index remains a fallback and independent cross-check.

All adapters return a common `DailyEdition`/note representation and explicit source metadata. Empty source responses are accepted only as a `no_edition` result when the adapter can distinguish them from malformed or contradictory responses.

### 2. Source registry

A registry records source id, base URL, authority, format, capabilities, and priority. `sidof` and `dof_index` are authoritative primary-government sources. `tavily` is `discovery_only` and has no authority score.

### 3. Deterministic monitor and provenance

Keep SHA-256 manifests, normalized JSON, stable note ids, human-readable diffs, rule evidence, and source URLs. Source and parser failures remain hard failures. A legitimate day without a gazette is represented as `no_edition` and must not fail CI/scheduled runs.

### 4. Searchable corpus

Build a local SQLite corpus from normalized records. SQLite FTS5 provides exact/lexical retrieval with filters by date, edition, issuer, type and topic. This avoids adding a hosted vector database. The first version indexes titles and available text/summary fields; future embedding retrieval can be added without changing the canonical corpus schema.

### 5. Optional Tavily discovery

If `TAVILY_API_KEY` is set, the discovery client can search/map official domains to identify candidate official URLs when known source patterns stop working. Results are restricted to `dof.gob.mx` and `sidof.segob.gob.mx`, are marked discovery-only, and must pass domain validation before any adapter consumes them. The scheduled monitor does not require Tavily to succeed.

### 6. Query interface

Add a CLI module that rebuilds the corpus from `data/normalized` and searches it. This makes the repository useful even with no external AI key. Results always include publication date, source URL and note code so an LLM or human can cite the official source.

## Failure semantics

- `no_edition`: valid source response with no publication for the requested date. Exit 0, write manifest/state/diff.
- `source_error`: network, HTTP, TLS or unavailable source after bounded retries/fallback. Exit nonzero.
- `parse_error`: response exists but violates the expected contract or claims the wrong date. Exit nonzero.
- `changed`: canonical catalog differs from prior canonical catalog.
- `no_change`: canonical catalog is identical.

## Testing

Tests must cover: weekend/no-publication behavior, malformed HTML still failing, SIDOF normalization, fallback to DOF HTML, source-domain validation for Tavily, FTS corpus build/search, and workflow behavior. CI runs all tests on Python 3.12. No test may require live network access or secrets.

## Non-goals

- No automatic legal conclusions, legal-effect classification, or claim that an AI answer is authoritative.
- No dependency on Tavily, embeddings, a hosted vector DB, Selenium or browser automation for normal scheduled runs.
- No republishing full DOF PDFs/Word files in git.
