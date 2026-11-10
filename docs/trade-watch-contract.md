# DOF trade-change triage: offline review feed

**Status: experimental.** This facility searches the **title** of records that DOF Intelligence Lab already normalized from the official SIDOF service or the official DOF index. It does not download an instrument, interpret the body text, decide when a decree takes effect, issue a legal opinion, or modify published tariff data.

## Usage

```bash
python3 -m dof_diff_lab sync --date 2026-11-10 --root .
python3 -m dof_diff_lab triage --root . --start 2026-11-01 --end 2026-11-10 --limit 100
```

The second command **does not access the internet**. It reads `data/normalized/YYYY-MM-DD/<edition>.json` files previously written by sync. This is preferable to directly ingesting unknown web search results. Date ranges use ISO dates. A missing or not-yet-synchronized day cannot be interpreted as an absence of news. No GitHub issues, notifications, releases or dataset updates are performed by triage.

## Candidate contract

The output JSON has:

- `schema_version` and `rule_version`, plus a disclaimer that a **title match is not a legal change**.
- `status` `no_local_catalogs` or `scan_complete`. The former reflects **no locally eligible catalogs**, not zero DOF publications.
- `coverage.local_catalogs_scanned`, `notes_with_official_url_and_title`, `notes_missing_title`, `notes_rejected_nonofficial_url`, `candidate_total`, and `results_truncated`.
- `candidates[]`, each with publication date, edition, code, official HTTPS URL, title, issuer, source ID, original `record_sha256` where available, source catalog path relative to `data/normalized`, deterministic `signals[]`, and `review_status=unverified_title_match`.

Each `signal` specifies `rule_id`, `family` (`tariff` or `trade_regulation`), `matched_text` and `evidence_surface=title`. The current rules distinguish explicit **TIGIE/LIGIE/NICO/fracción/arancel** keywords from **RGCE/RRNA/permiso previo/cupo**. A generic title mentioning "importación", "comercio exterior" or an agency, by itself, is **not enough** to infer a tariff change. The first family receives internal label `priority_review`, but this label does **not** mean the item has greater legal importance. Missing titles and non-official HTTPS URLs are excluded and explicitly counted.

### Sample shape (illustrative, not an actual DOF notice)

```json
{
  "schema_version": "1.0",
  "rule_version": "trade-title-v1",
  "status": "scan_complete",
  "coverage": {
    "local_catalogs_scanned": 1,
    "notes_with_official_url_and_title": 1,
    "notes_missing_title": 0,
    "notes_rejected_nonofficial_url": 0,
    "candidate_total": 1,
    "results_truncated": false
  },
  "candidates": [
    {
      "publication_date": "2026-11-10",
      "edition": "matutina",
      "code": "101",
      "title": "Decreto por el que se modifica la TIGIE",
      "canonical_url": "https://sidof.segob.gob.mx/notas/101",
      "source_id": "sidof",
      "record_sha256": "record hash from source catalog",
      "source_catalog": "2026-11-10/matutina.json",
      "priority": "priority_review",
      "signals": [{"rule_id": "trade-title-v1.tariff.02", "family": "tariff", "matched_text": "tigie", "evidence_surface": "title"}],
      "review_status": "unverified_title_match"
    }
  ]
}
```

The sample omits the `filters`, `disclaimer` and other optional fields for brevity. Do not treat a sample code/URL as an actual published note.

## Trust boundary with arancel-mx

1. **Discovery:** `dof-diff-lab triage` identifies a candidate solely from a matching title; it is an *untrusted lead*, even when sourced from an official domain.
2. **Manual verification:** open the actual instrument, verify title, subject, effective date, legal scope, affected codes, appendices and relationships to existing instruments. Confirm identity/provenance and official publication.
3. **Tariff data pipeline:** only the **existing independent, fail-closed evidence chain** in `arancel-mx` can add/update legal instruments or publish a new immutable dataset. Never let this feed write its registry, DB, or GitHub release.
4. **User-facing narrative:** do not imply a detected candidate changed the TIGIE, a rate, an NICO, a permit or any legal obligation. The catalog may have false positives and false negatives.

**No mandatory coupling:** `arancel-mx` already has its own official SIDOF `scripts/watch_dof.py` monitor and manual-review issues. This triage output is a broad research signal, *not a replacement or duplicate publisher*. It also covers related trade-regulatory vocabulary not limited to tariff issues.

## Quality and limitations

The rule set is explicit and versioned. It is deterministic under equal local catalog files. Records are sorted, missing titles are counted, URL hostnames are restricted to DOF/SIDOF and local catalog date/edition mismatches fail closed. Case and accent folding are used for Spanish text. Tests are offline and include malicious URL, false positives, no-title records, invalid dates, duplicate keys and CLI output.

**Remaining risks:** title keywords can miss instruments that only mention affected tariff codes in annexes. The algorithm does not inspect texts or compare signed PDFs, and does not guarantee a complete legal or regulatory watch. A false negative can occur when the source publishes a generic title or SIDOF metadata is unavailable. Do not make business decisions without independent validation of the official primary document.

```bash
python3 tests/check_trade_watch.py
```
