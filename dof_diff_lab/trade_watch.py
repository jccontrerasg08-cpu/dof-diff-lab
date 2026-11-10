"""Offline title-based trade watch over previously normalized DOF catalogs.

A match is a review CANDIDATE, never a certified legal change. This module
does not fetch official sites, infer effect/validity or modify arancel-mx data.
It does not read private systems or create GitHub issues.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from .monitor import folded_text

SCHEMA_VERSION = "1.0"
RULE_VERSION = "trade-title-v1"
OFFICIAL_HOSTS = frozenset({"dof.gob.mx", "www.dof.gob.mx", "sidof.segob.gob.mx"})

# Specific title signals only. General issuer/agency or "importación"
# alone is insufficient evidence that tariff or customs policy changed.
RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "tariff",
        "priority_review",
        (
            r"\bligie\b",
            r"\btigie\b",
            r"\bnico\b",
            r"\bfraccion(?:es)? arancelaria(?:s)?\b",
            r"(?<!no )\barancel(?:es|aria|arias|ario|arios)?\b",
            r"\btarifa de la ley de los impuestos generales de importacion y de exportacion\b",
        ),
    ),
    (
        "trade_regulation",
        "review",
        (
            r"\breglas generales de comercio exterior\b",
            r"\brgce\b",
            r"\bregulaciones y restricciones no arancelarias\b",
            r"\brrna\b",
            r"\bpermisos? previos? de (?:importacion|exportacion)\b",
            r"\bcupos? (?:de )?(?:importacion|exportacion|arancelarios?)\b",
        ),
    ),
)
def _official_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
        return (
            parts.scheme == "https"
            and parts.hostname in OFFICIAL_HOSTS
            and parts.username is None
            and parts.password is None
            and parts.port is None
        )
    except ValueError:
        return False


def _date(value: str) -> date:
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Expected ISO publication date YYYY-MM-DD") from exc
    if result.isoformat() != value:
        raise ValueError("Expected ISO publication date YYYY-MM-DD")
    return result


def title_signals(title: str) -> list[dict[str, str]]:
    """Return reproducible explicit word/phrase matches, no legal inference."""
    folded = folded_text(title)
    result: list[dict[str, str]] = []
    for family, priority, patterns in RULES:
        for index, expression in enumerate(patterns, start=1):
            match = re.search(expression, folded, flags=re.IGNORECASE)
            if match:
                result.append(
                    {
                        "rule_id": f"{RULE_VERSION}.{family}.{index:02d}",
                        "family": family,
                        "priority": priority,
                        "matched_text": match.group(0),
                        "evidence_surface": "title",
                    }
                )
                break  # one evidence item per family to limit noise
    return result


def scan_trade_candidates(
    normalized_root: Path,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Read ONLY local normalized catalogs. Returns stable JSON-compatible data.

    A missing dataset is not proof of no publications. A malformed catalog
    fails closed. Missing titles and non-official URLs are counted but never
    silently promoted. Results are sorted by publication date, edition, code,
    URL so repeated scans are identical.
    """
    if start is not None and end is not None and start > end:
        raise ValueError("start date must be on or before end date")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
        raise ValueError("limit must be an integer in 1..10000")
    root = Path(normalized_root)
    files = sorted(root.glob("*/*.json"))
    candidates: list[dict[str, Any]] = []
    catalog_count = eligible_notes = excluded_missing_title = excluded_invalid_url = 0
    seen: set[tuple[str, str, str, str]] = set()

    for path in files:
        publication_date = _date(path.parent.name)
        if start is not None and publication_date < start:
            continue
        if end is not None and publication_date > end:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
            raise ValueError(f"Invalid normalized catalog: {path}")
        source = payload.get("source")
        if not isinstance(source, dict) or source.get("publication_date") != publication_date.isoformat():
            raise ValueError(f"Catalog source date does not match path: {path}")
        edition = source.get("edition")
        if not isinstance(edition, str) or edition != path.stem:
            raise ValueError(f"Catalog edition does not match path: {path}")
        catalog_count += 1
        for note in payload["notes"]:
            if not isinstance(note, dict):
                raise ValueError(f"Invalid DOF record in: {path}")
            title = note.get("title")
            if note.get("title_available", True) is False or not isinstance(title, str) or not title.strip():
                excluded_missing_title += 1
                continue
            url = note.get("canonical_url")
            if not _official_url(url):
                excluded_invalid_url += 1
                continue
            eligible_notes += 1
            signals = title_signals(title)
            if not signals:
                continue
            code = note.get("code")
            code = str(code) if code is not None else ""
            key = (publication_date.isoformat(), edition, code, str(url))
            if key in seen:
                raise ValueError(f"Duplicate DOF note key: {key}")
            seen.add(key)
            priority = "priority_review" if any(
                signal["priority"] == "priority_review" for signal in signals
            ) else "review"
            candidates.append(
                {
                    "publication_date": publication_date.isoformat(),
                    "edition": edition,
                    "code": code,
                    "title": title,
                    "canonical_url": url,
                    "source_id": note.get("source_id") or source.get("source_id"),
                    "record_sha256": note.get("record_sha256"),
                    "issuer": note.get("issuer_secondary") or note.get("issuer_primary"),
                    "source_catalog": str(path.relative_to(root)),
                    "priority": priority,
                    "signals": signals,
                    "review_status": "unverified_title_match",
                }
            )

    candidates.sort(
        key=lambda item: (
            item["publication_date"], item["edition"], item["code"],
            item["canonical_url"],
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "status": "no_local_catalogs" if catalog_count == 0 else "scan_complete",
        "disclaimer": (
            "Title matches are review candidates only. An official publication "
            "may or may not alter a tariff, trade rule or legal validity. "
            "Verify the full official text and effective dates manually."
        ),
        "filters": {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "limit": limit,
        },
        "coverage": {
            "local_catalogs_scanned": catalog_count,
            "notes_with_official_url_and_title": eligible_notes,
            "notes_missing_title": excluded_missing_title,
            "notes_rejected_nonofficial_url": excluded_invalid_url,
            "candidate_total": len(candidates),
            "results_truncated": len(candidates) > limit,
        },
        "candidates": candidates[:limit],
    }


def parse_iso_date(value: str) -> date:
    """ArgumentParser type adapter, rejecting noncanonical ISO strings."""
    return _date(value)
