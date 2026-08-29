# DOF Intelligence Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scheduled monitoring resilient, add structured SIDOF ingestion with DOF fallback, add a searchable local corpus, and add optional Tavily discovery restricted to official domains.

**Architecture:** Preserve the deterministic monitor as the canonical provenance layer. Add small source/corpus/discovery modules with explicit interfaces, then extend CI with network-free tests.

**Tech Stack:** Python 3.12 stdlib, SQLite FTS5, urllib, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-29-dof-intelligence-corpus-design.md`

## Global Constraints

- Official DOF/SIDOF sources remain authoritative.
- Tavily is optional and discovery-only.
- Scheduled runs require no external secrets.
- No live-network dependency in tests.
- Valid no-publication days exit successfully as `no_edition`.

---

### Task 1: Fix no-edition semantics

**Files:** `tests/check_monitor.py`, `dof_diff_lab/monitor.py`

- [ ] Add a failing fixture representing a source page with no edition marker and no notes.
- [ ] Verify current parser raises `ParseError`.
- [ ] Add conservative `looks_like_no_edition()` detection while retaining hard failure for malformed content.
- [ ] Verify monitor emits `no_edition`, artifacts, and exit 0.

### Task 2: Add source registry and SIDOF adapter

**Files:** create `dof_diff_lab/sources.py`, create `tests/check_sources.py`

- [ ] Test registry priorities and official-domain validation.
- [ ] Test SIDOF date-response normalization for empty and populated days.
- [ ] Implement stdlib JSON fetch/normalization interfaces with no live network in tests.

### Task 3: Add searchable corpus

**Files:** create `dof_diff_lab/corpus.py`, create `tests/check_corpus.py`

- [ ] Test building SQLite from normalized JSON fixtures.
- [ ] Test FTS title/topic/issuer retrieval and provenance fields.
- [ ] Implement deterministic rebuild and search APIs.

### Task 4: Add optional Tavily discovery

**Files:** create `dof_diff_lab/discovery.py`, create `tests/check_discovery.py`

- [ ] Test that non-official candidate URLs are rejected.
- [ ] Test missing API key is a safe disabled state.
- [ ] Implement `/search` request using stdlib HTTP and domain allowlist; never use results as authority.

### Task 5: Add CLI and CI coverage

**Files:** create `dof_diff_lab/intelligence.py`, modify `.github/workflows/check.yml`, modify `README.md`

- [ ] Add `build` and `search` commands for corpus.
- [ ] Add new checks to CI.
- [ ] Document source hierarchy, Tavily secret, corpus commands and failure semantics.
- [ ] Open PR and verify GitHub Actions passes.
