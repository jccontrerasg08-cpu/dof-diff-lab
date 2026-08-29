from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    code TEXT,
    publication_date TEXT NOT NULL,
    edition TEXT,
    issuer TEXT,
    document_type TEXT,
    topic TEXT,
    title TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_path TEXT NOT NULL,
    UNIQUE(code, publication_date, edition, canonical_url)
);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title,
    issuer,
    document_type,
    topic,
    content='notes',
    content_rowid='id'
);
"""


def _tag_value(note: dict[str, object], name: str) -> str:
    values: list[str] = []
    for item in note.get("tags", []):
        if isinstance(item, dict) and item.get("name") == name and item.get("value"):
            values.append(str(item["value"]))
    return " ".join(values)


def _fts_query(query: str) -> str | None:
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    if not tokens:
        return None
    return " ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def build_corpus(normalized_root: Path, database_path: Path) -> int:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.execute("DELETE FROM notes_fts")
        connection.execute("DELETE FROM notes")
        count = 0
        for path in sorted(normalized_root.glob("*/*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            source = payload.get("source", {}) if isinstance(payload, dict) else {}
            publication_date = str(source.get("publication_date") or path.parent.name)
            edition = str(source.get("edition") or path.stem)
            for note in payload.get("notes", []):
                if not isinstance(note, dict) or not note.get("title") or not note.get("canonical_url"):
                    continue
                issuer = note.get("issuer_secondary") or note.get("issuer_primary") or ""
                cursor = connection.execute(
                    """INSERT INTO notes(code, publication_date, edition, issuer, document_type, topic, title, canonical_url, source_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(note.get("code") or ""), publication_date, edition, str(issuer),
                        _tag_value(note, "document_type"), _tag_value(note, "topic"),
                        str(note["title"]), str(note["canonical_url"]), str(path),
                    ),
                )
                rowid = cursor.lastrowid
                connection.execute(
                    "INSERT INTO notes_fts(rowid, title, issuer, document_type, topic) VALUES (?, ?, ?, ?, ?)",
                    (rowid, str(note["title"]), str(issuer), _tag_value(note, "document_type"), _tag_value(note, "topic")),
                )
                count += 1
        connection.commit()
    return count


def search_corpus(database_path: Path, query: str, limit: int = 10) -> list[dict[str, str]]:
    match_query = _fts_query(query)
    if match_query is None or limit < 1:
        return []
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT n.code, n.publication_date, n.edition, n.issuer, n.document_type, n.topic,
                      n.title, n.canonical_url, bm25(notes_fts) AS score
               FROM notes_fts JOIN notes n ON notes_fts.rowid = n.id
               WHERE notes_fts MATCH ?
               ORDER BY score ASC, n.publication_date DESC
               LIMIT ?""",
            (match_query, limit),
        ).fetchall()
    return [{key: str(row[key] if row[key] is not None else "") for key in row.keys()} for row in rows]
