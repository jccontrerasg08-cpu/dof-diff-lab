from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Callable

from .corpus import build_corpus, search_corpus
from .discovery import tavily_search
from .monitor import (
    MonitorResult,
    ParseError,
    SourceResponse,
    build_index_url,
    build_insights,
    canonical_bytes,
    derive_tags,
    diff_catalogs,
    fetch_official_index,
    load_catalog,
    render_diff,
    render_site,
    run_monitor,
    sha256_bytes,
    utc_now,
    write_json,
)
from .sources import fetch_sidof_notes, sidof_notes_url


def _canonical_sidof_note(note: dict[str, object]) -> dict[str, object]:
    title = str(note["title"])
    value = {
        "code": str(note.get("code") or ""),
        "canonical_url": str(note["canonical_url"]),
        "title": title,
        "section": note.get("section"),
        "issuer_primary": note.get("issuer_primary"),
        "issuer_secondary": note.get("issuer_secondary"),
        "source_id": "sidof",
        "tags": derive_tags(title),
    }
    value["record_sha256"] = sha256_bytes(canonical_bytes(value))
    return value


def _write_sidof_date(publication_date: date, root: Path, notes: list[dict[str, object]]) -> dict[str, object]:
    date_key = publication_date.isoformat()
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for note in notes:
        grouped[str(note.get("edition") or "desconocida")].append(_canonical_sidof_note(note))

    flattened: list[dict[str, object]] = []
    changed_any = False
    edition_manifests: list[str] = []
    for edition in sorted(grouped):
        canonical_notes = sorted(grouped[edition], key=lambda item: (str(item.get("code") or ""), str(item["canonical_url"])))
        flattened.extend(canonical_notes)
        normalized_path = root / "data" / "normalized" / date_key / f"{edition}.json"
        previous = load_catalog(normalized_path)
        catalog = {
            "schema_version": "1.1",
            "source": {
                "name": "SIDOF open data",
                "source_id": "sidof",
                "publication_date": date_key,
                "edition": edition,
                "index_url": sidof_notes_url(publication_date),
            },
            "notes": canonical_notes,
        }
        changes = diff_catalogs(previous, catalog)
        changed = any(changes.values())
        changed_any = changed_any or changed
        write_json(normalized_path, catalog)
        manifest = {
            "schema_version": "1.1",
            "parser_version": "sidof-1.1",
            "status": "changed" if changed else "no_change",
            "generated_at": utc_now(),
            "publication_date": date_key,
            "edition": edition,
            "note_count": len(canonical_notes),
            "source": {"source_id": "sidof", "authority": "primary", "url": catalog["source"]["index_url"]},
            "normalized_path": str(normalized_path.relative_to(root)),
            "normalized_sha256": sha256_bytes(canonical_bytes(catalog)),
            "insights": build_insights(canonical_notes),
        }
        manifest_path = root / "data" / "manifests" / date_key / f"{edition}.json"
        write_json(manifest_path, manifest)
        edition_manifests.append(str(manifest_path.relative_to(root)))
        diff_path = root / "data" / "diffs" / f"{date_key}-{edition}.md"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(render_diff(publication_date, changes), encoding="utf-8")

    status = "changed" if changed_any else "no_change"
    summary = {
        "status": status,
        "publication_date": date_key,
        "source_id": "sidof",
        "editions": sorted(grouped),
        "note_count": len(flattened),
        "manifests": edition_manifests,
        "updated_at": utc_now(),
    }
    write_json(root / "data" / "state" / "latest.json", summary)
    site_manifest = {"status": status, "publication_date": date_key, "note_count": len(flattened), "insights": build_insights(flattened)}
    site_path = root / "site" / "index.html"
    site_path.parent.mkdir(parents=True, exist_ok=True)
    site_path.write_text(render_site(site_manifest, flattened), encoding="utf-8")
    (site_path.parent / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    return summary


def _write_confirmed_no_edition(publication_date: date, root: Path, dof_response: SourceResponse) -> dict[str, object]:
    date_key = publication_date.isoformat()
    edition = "matutina"
    normalized_path = root / "data" / "normalized" / date_key / f"{edition}.json"
    catalog = {
        "schema_version": "1.1",
        "source": {
            "name": "SIDOF + DOF cross-check",
            "source_id": "sidof+dof_index",
            "publication_date": date_key,
            "edition": edition,
            "sidof_url": sidof_notes_url(publication_date),
            "dof_index_url": build_index_url(publication_date),
        },
        "notes": [],
    }
    write_json(normalized_path, catalog)
    manifest = {
        "schema_version": "1.1",
        "parser_version": "hybrid-1.1",
        "status": "no_edition",
        "generated_at": utc_now(),
        "publication_date": date_key,
        "edition": edition,
        "note_count": 0,
        "source": {
            "source_id": "sidof+dof_index",
            "authority": "primary",
            "sidof_empty": True,
            "sidof_url": sidof_notes_url(publication_date),
            "dof_index_url": build_index_url(publication_date),
            "dof_http_status": dof_response.status,
            "dof_content_type": dof_response.content_type,
            "dof_raw_sha256": sha256_bytes(dof_response.body),
            "dof_raw_retained": False,
        },
        "normalized_path": str(normalized_path.relative_to(root)),
        "normalized_sha256": sha256_bytes(canonical_bytes(catalog)),
        "insights": build_insights([]),
    }
    manifest_path = root / "data" / "manifests" / date_key / f"{edition}.json"
    write_json(manifest_path, manifest)
    diff_path = root / "data" / "diffs" / f"{date_key}.md"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(f"# Monitor DOF — {date_key}\n\nSin publicaciones confirmadas para la fecha consultada.\n", encoding="utf-8")
    summary = {
        "status": "no_edition",
        "publication_date": date_key,
        "source_id": "sidof+dof_index",
        "editions": [],
        "note_count": 0,
        "manifests": [str(manifest_path.relative_to(root))],
        "updated_at": manifest["generated_at"],
    }
    write_json(root / "data" / "state" / "latest.json", summary)
    site_path = root / "site" / "index.html"
    site_path.parent.mkdir(parents=True, exist_ok=True)
    site_path.write_text(render_site({"status": "no_edition", "publication_date": date_key, "note_count": 0, "insights": build_insights([])}, []), encoding="utf-8")
    (site_path.parent / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    return summary


def sync_date(
    publication_date: date,
    root: Path,
    sidof_fetch: Callable[[date], list[dict[str, object]]] = fetch_sidof_notes,
    dof_fetch: Callable[[str], SourceResponse] = fetch_official_index,
) -> dict[str, object]:
    sidof_error: Exception | None = None
    try:
        notes = sidof_fetch(publication_date)
    except Exception as error:
        sidof_error = error
        notes = []

    if notes:
        return _write_sidof_date(publication_date, root, notes)

    index_url = build_index_url(publication_date)
    dof_response = dof_fetch(index_url)
    try:
        result: MonitorResult = run_monitor(publication_date, root, fetch=lambda _url: dof_response)
    except ParseError:
        if sidof_error is None and publication_date.weekday() >= 5:
            return _write_confirmed_no_edition(publication_date, root, dof_response)
        raise
    return {
        "status": result.status,
        "publication_date": publication_date.isoformat(),
        "source_id": "dof_index",
        "note_count": result.note_count,
        "sidof_error": str(sidof_error) if sidof_error else None,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DOF Intelligence: sync, corpus search and optional official-domain discovery.")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Sync one date from SIDOF with DOF HTML fallback.")
    sync.add_argument("--date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    sync.add_argument("--root", type=Path, default=Path("."))

    build = sub.add_parser("build", help="Rebuild the local SQLite FTS corpus.")
    build.add_argument("--root", type=Path, default=Path("."))
    build.add_argument("--database", type=Path, default=Path(".tmp/dof-corpus.sqlite3"))

    search = sub.add_parser("search", help="Search a built local corpus.")
    search.add_argument("query")
    search.add_argument("--database", type=Path, default=Path(".tmp/dof-corpus.sqlite3"))
    search.add_argument("--limit", type=int, default=10)

    discover = sub.add_parser("discover", help="Optional Tavily discovery restricted to official DOF/SIDOF domains.")
    discover.add_argument("query")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "sync":
            result = sync_date(args.date, args.root.resolve())
        elif args.command == "build":
            count = build_corpus(args.root.resolve() / "data" / "normalized", args.database)
            result = {"database": str(args.database), "documents": count}
        elif args.command == "search":
            result = {"results": search_corpus(args.database, args.query, args.limit)}
        else:
            result = {"urls": tavily_search(args.query)}
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
