from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen
import unicodedata


SCHEMA_VERSION = "1.0"
PARSER_VERSION = "1.0"
RULE_VERSION = "1.0"
EDITION = "matutina"


@dataclass(frozen=True)
class SourceResponse:
    """A single read-only response from the official DOF index."""

    status: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class MonitorResult:
    """The deterministic outcome of one daily monitor run."""

    status: str
    note_count: int
    index_url: str
    normalized_sha256: str


class SourceError(ValueError):
    """Raised when the official source cannot be used as a trustworthy capture."""


class ParseError(ValueError):
    """Raised when a source response cannot be normalized safely."""


def build_index_url(publication_date: date) -> str:
    """Return the observed official URL pattern for a matutina DOF index."""

    return (
        "https://dof.gob.mx/index_113.php?"
        f"year={publication_date:%Y}&month={publication_date:%m}&day={publication_date:%d}"
    )


def utc_now() -> str:
    """Return an ISO-8601 timestamp with an explicit UTC offset."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_bytes(value: object) -> bytes:
    """Serialize JSON deterministically for hashing and version control."""

    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    """Return a hexadecimal SHA-256 digest."""

    return sha256(value).hexdigest()


def normalized_text(value: str) -> str:
    """Normalize display text without erasing the original source field."""

    return " ".join(value.split())


def folded_text(value: str) -> str:
    """Fold accents and case for deterministic, explainable rule matching."""

    decomposed = unicodedata.normalize("NFD", value)
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn").lower()


class OfficialIndexParser(HTMLParser):
    """Extract note links and nearby editorial context from an official index page."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.notes: list[dict[str, object]] = []
        self.section: str | None = None
        self.issuer_primary: str | None = None
        self.issuer_secondary: str | None = None
        self.observed_edition = False
        self._anchor_href: str | None = None
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href and "nota_detalle.php" in href:
            self._anchor_href = urljoin(self.base_url, href)
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._anchor_href is not None:
            self._anchor_parts.append(data)
            return
        self._update_context(normalized_text(data))

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._anchor_href is None:
            return
        title = normalized_text(" ".join(self._anchor_parts))
        href = self._anchor_href
        self._anchor_href = None
        self._anchor_parts = []
        if not title:
            return
        code = parse_qs(urlsplit(href).query).get("codigo", [None])[0]
        self.notes.append(
            {
                "code": code,
                "canonical_url": href,
                "title": title,
                "section": self.section,
                "issuer_primary": self.issuer_primary,
                "issuer_secondary": self.issuer_secondary,
            }
        )

    def _update_context(self, value: str) -> None:
        if not value or len(value) < 3 or value.startswith("Ver "):
            return
        folded = folded_text(value)
        if "fecha:" in folded and "edicion" in folded:
            self.observed_edition = True
        if folded in {"primera", "segunda", "tercera", "unica seccion"}:
            self.section = value
            return
        if value != value.upper() or any(character.islower() for character in value):
            return
        if value.startswith(("PODER ", "ORGANISMOS ", "TRIBUNAL ")):
            self.issuer_primary = value
            self.issuer_secondary = None
            return
        if self.issuer_primary and not any(token in folded for token in ("ver word", "ver imagen")):
            self.issuer_secondary = value


def tag(name: str, value: str, evidence: str, rule_id: str, confidence: str = "rule_match") -> dict[str, str]:
    """Create one self-explaining derived tag."""

    return {
        "name": name,
        "value": value,
        "evidence": evidence,
        "rule_id": rule_id,
        "rule_version": RULE_VERSION,
        "confidence": confidence,
    }


def first_match(text: str, expressions: tuple[str, ...]) -> str | None:
    """Return the first exact source fragment that activates a deterministic rule."""

    for expression in expressions:
        match = re.search(expression, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def derive_tags(title: str) -> list[dict[str, str]]:
    """Create conservative document, signal and topic tags from a source title."""

    folded = folded_text(title)
    tags: list[dict[str, str]] = []

    document_types = (
        ("acuerdo", (r"^acuerdo\b",)),
        ("decreto", (r"^decreto\b",)),
        ("resolucion", (r"^resolucion\b",)),
        ("norma", (r"^norma\b", r"\bnorma oficial mexicana\b", r"\bnmx[- ]")),
        ("convenio", (r"^convenio\b",)),
        ("aviso", (r"^aviso\b",)),
        ("circular", (r"^circular\b",)),
        ("sentencia", (r"^sentencia\b",)),
        ("convocatoria", (r"^convocatoria\b",)),
    )
    for value, expressions in document_types:
        evidence = first_match(folded, expressions)
        if evidence:
            tags.append(tag("document_type", value, evidence, f"document_type.{value}"))
            break
    else:
        tags.append(tag("document_type", "otro", title, "document_type.other", "low"))

    signals = (
        ("possible_modification", (r"\bmodifica\w*\b",)),
        ("possible_addition", (r"\badiciona\w*\b",)),
        ("possible_repeal", (r"\bderoga\w*\b",)),
        ("possible_abrogation", (r"\babroga\w*\b",)),
        ("contains_effective_date", (r"\bentra en vigor\b", r"\bvigencia\b")),
        ("contains_deadline", (r"\bplazo\b", r"\bfecha limite\b")),
        ("contains_call_for_bids", (r"\bconvocatoria\b", r"\blicitacion\b")),
    )
    for value, expressions in signals:
        evidence = first_match(folded, expressions)
        if evidence:
            tags.append(tag("signal", value, evidence, f"signal.{value}"))

    topics = (
        ("fiscal", (r"\bfiscal\b", r"\bhacienda\b", r"\bimpuesto\w*\b", r"\btributari\w*\b")),
        ("trade", (r"\bcomercio exterior\b", r"\baduan\w*\b", r"\barancel\w*\b", r"\bimportacion\b", r"\bexportacion\b")),
        ("labor", (r"\blaboral\b", r"\btrabajad\w*\b", r"\bempleo\b")),
        ("health", (r"\bsalud\b", r"\bsanitari\w*\b", r"\bcofepris\b")),
        ("environment", (r"\bambient\w*\b", r"\becologi\w*\b", r"\bagua\w*\b")),
        ("energy", (r"\benergia\b", r"\bpetrol\w*\b", r"\belectric\w*\b")),
        ("financial", (r"\bfinancier\w*\b", r"\bbanco\b", r"\btiie\b", r"\btasa de interes\b")),
        ("public_procurement", (r"\blicitacion\b", r"\badquisicion\w*\b", r"\bcontratacion\b")),
        ("data_protection", (r"\bdatos personales\b", r"\bprivacidad\b")),
    )
    for value, expressions in topics:
        evidence = first_match(folded, expressions)
        if evidence:
            tags.append(tag("topic", value, evidence, f"topic.{value}"))
    if not any(item["name"] == "topic" for item in tags):
        tags.append(tag("topic", "other", title, "topic.other", "low"))
    return tags


def note_key(note: dict[str, object]) -> str:
    """Return a stable monitor identity, preferring the official note code."""

    code = note.get("code")
    if isinstance(code, str) and code:
        return code
    return str(note["canonical_url"])


def build_note(raw_note: dict[str, object]) -> dict[str, object]:
    """Build a canonical note with only source fields and explainable derivations."""

    title = str(raw_note["title"])
    note = {
        "code": raw_note.get("code"),
        "canonical_url": raw_note["canonical_url"],
        "title": title,
        "section": raw_note.get("section"),
        "issuer_primary": raw_note.get("issuer_primary"),
        "issuer_secondary": raw_note.get("issuer_secondary"),
        "tags": derive_tags(title),
    }
    note["record_sha256"] = sha256_bytes(canonical_bytes(note))
    return note


def parse_official_index(body: bytes, index_url: str) -> list[dict[str, object]]:
    """Normalize visible note links from an official index HTML response."""

    text = body.decode("utf-8", errors="replace")
    parser = OfficialIndexParser(index_url)
    parser.feed(text)
    parser.close()
    records: dict[str, dict[str, object]] = {}
    for raw_note in parser.notes:
        note = build_note(raw_note)
        key = note_key(note)
        if key in records:
            raise ParseError(f"El índice contiene una nota duplicada: {key}")
        records[key] = note
    if not records and not parser.observed_edition:
        raise ParseError("El índice oficial no contiene fecha y edición reconocibles.")
    return [records[key] for key in sorted(records)]


def load_catalog(path: Path) -> dict[str, object] | None:
    """Load a prior canonical catalog when it exists."""

    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("notes"), list):
        raise ParseError(f"El catálogo previo no tiene el esquema esperado: {path}")
    return value


def diff_catalogs(previous: dict[str, object] | None, current: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """Compare canonical notes by stable identity and record hash."""

    previous_notes = previous.get("notes", []) if previous else []
    previous_by_key = {note_key(note): note for note in previous_notes if isinstance(note, dict)}
    current_by_key = {note_key(note): note for note in current["notes"] if isinstance(note, dict)}
    return {
        "added": [current_by_key[key] for key in sorted(current_by_key.keys() - previous_by_key.keys())],
        "removed": [previous_by_key[key] for key in sorted(previous_by_key.keys() - current_by_key.keys())],
        "modified": [
            current_by_key[key]
            for key in sorted(current_by_key.keys() & previous_by_key.keys())
            if current_by_key[key].get("record_sha256") != previous_by_key[key].get("record_sha256")
        ],
    }


def render_diff(publication_date: date, changes: dict[str, list[dict[str, object]]]) -> str:
    """Render a compact human-readable diff without legal conclusions."""

    sections = [f"# Monitor DOF — {publication_date.isoformat()}\n"]
    labels = (("added", "Altas"), ("removed", "Bajas"), ("modified", "Modificaciones"))
    if not any(changes.values()):
        return "\n".join((*sections, "Sin cambios en el catálogo normalizado.\n"))
    for key, label in labels:
        notes = changes[key]
        sections.append(f"## {label} ({len(notes)})\n")
        for note in notes:
            sections.append(f"- [{note_key(note)}] {note['title']} — {note['canonical_url']}\n")
    return "\n".join(sections)


def build_insights(notes: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    """Count only deterministic labels; these are operational insights, not advice."""

    by_document_type: dict[str, int] = {}
    by_topic: dict[str, int] = {}
    by_issuer: dict[str, int] = {}
    for note in notes:
        issuer = note.get("issuer_secondary") or note.get("issuer_primary") or "SIN_EMISOR"
        by_issuer[str(issuer)] = by_issuer.get(str(issuer), 0) + 1
        for item in note["tags"]:
            if item["name"] == "document_type":
                by_document_type[item["value"]] = by_document_type.get(item["value"], 0) + 1
            if item["name"] == "topic":
                by_topic[item["value"]] = by_topic.get(item["value"], 0) + 1
    return {
        "by_document_type": dict(sorted(by_document_type.items())),
        "by_topic": dict(sorted(by_topic.items())),
        "by_issuer": dict(sorted(by_issuer.items())),
    }


def write_json(path: Path, value: object) -> None:
    """Write deterministic JSON after creating the parent directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def render_site(manifest: dict[str, object], notes: list[dict[str, object]]) -> str:
    """Render a public, source-linked index without republishing source HTML."""

    insights = manifest["insights"]
    document_types = "".join(
        f"<li>{escape(name)}: {count}</li>" for name, count in insights["by_document_type"].items()
    )
    topics = "".join(f"<li>{escape(name)}: {count}</li>" for name, count in insights["by_topic"].items())
    evidence_items: list[str] = []
    for note in notes:
        tags = "".join(
            "<li>"
            f"{escape(str(item['name']))}: {escape(str(item['value']))}. "
            f"Regla: {escape(str(item['rule_id']))} ({escape(str(item['rule_version']))}). "
            f"Evidencia: {escape(str(item['evidence']))}. "
            "Coincidencia de regla; no probabilidad ni conclusión jurídica."
            "</li>"
            for item in note["tags"]
        )
        evidence_items.append(
            "<article><h3>"
            f"<a href=\"{escape(str(note['canonical_url']))}\">{escape(str(note['code'] or 'sin código'))}</a> "
            f"{escape(str(note['title']))}</h3><ul>{tags}</ul></article>"
        )
    return "".join(
        (
            "<!doctype html><html lang=\"es\"><meta charset=\"utf-8\">",
            "<meta name=\"robots\" content=\"noindex,nofollow\">",
            "<title>Monitor diario del DOF</title>",
            "<main><h1>Monitor diario del DOF</h1>",
            "<p><strong>No afiliación:</strong> este proyecto no está afiliado, patrocinado ni respaldado por el Diario Oficial de la Federación.</p>",
            "<p><strong>Fuente primaria:</strong> prevalece la publicación oficial enlazada. Este catálogo derivado no sustituye la fuente oficial ni constituye asesoría jurídica.</p>",
            f"<p>Estado: <strong>{escape(str(manifest['status']))}</strong></p>",
            f"<p>Fecha de publicación: {escape(str(manifest['publication_date']))}</p>",
            f"<p>Notas: {manifest['note_count']}</p>",
            "<h2>Tipos documentales</h2><ul>", document_types, "</ul>",
            "<h2>Temas detectados por reglas</h2><ul>", topics, "</ul>",
            "<h2>Coincidencias de reglas y evidencia</h2>",
            "<p>Las etiquetas describen coincidencias deterministas en títulos y metadatos; no determinan vigencia, alcance ni efecto jurídico.</p>",
            "".join(evidence_items),
            "</main>",
        )
    )


def fetch_official_index(
    url: str,
    attempts: int = 3,
    opener: Callable[..., object] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> SourceResponse:
    """Fetch one official index with bounded retries for transient network failures."""

    if attempts < 1:
        raise ValueError("attempts debe ser al menos 1.")
    request = Request(url, headers={"User-Agent": "dof-diff-lab-monitor/1.0 (+https://github.com/jccontrerasg08-cpu/dof-diff-lab)"})
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            with opener(request, timeout=30) as response:
                return SourceResponse(
                    status=response.status,
                    content_type=response.headers.get_content_type(),
                    body=response.read(),
                )
        except OSError as error:
            last_error = error
            if attempt + 1 < attempts:
                sleeper(float(2**attempt))
    raise SourceError(f"No se pudo consultar el índice oficial del DOF: {last_error}") from last_error


def run_monitor(
    publication_date: date,
    root: Path,
    fetch: Callable[[str], SourceResponse] = fetch_official_index,
) -> MonitorResult:
    """Capture, normalize and compare one official DOF edition deterministically."""

    index_url = build_index_url(publication_date)
    response = fetch(index_url)
    if response.status != 200:
        raise SourceError(f"El índice oficial respondió HTTP {response.status}.")
    if "html" not in response.content_type:
        raise SourceError(f"El índice oficial respondió con MIME inesperado: {response.content_type}.")
    raw_sha256 = sha256_bytes(response.body)
    notes = parse_official_index(response.body, index_url)
    date_key = publication_date.isoformat()
    normalized_path = root / "data" / "normalized" / date_key / "matutina.json"
    previous = load_catalog(normalized_path)
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "name": "DOF official index",
            "index_url": index_url,
            "publication_date": date_key,
            "edition": EDITION,
        },
        "notes": notes,
    }
    changes = diff_catalogs(previous, catalog)
    if not notes:
        status = "no_edition"
    else:
        status = "changed" if any(changes.values()) else "no_change"
    normalized_sha256 = sha256_bytes(canonical_bytes(catalog))

    write_json(normalized_path, catalog)

    insights = build_insights(notes)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "status": status,
        "generated_at": utc_now(),
        "publication_date": date_key,
        "edition": EDITION,
        "note_count": len(notes),
        "source": {
            "index_url": index_url,
            "http_status": response.status,
            "content_type": response.content_type,
            "raw_sha256": raw_sha256,
            "raw_retained": False,
            "raw_size": len(response.body),
        },
        "normalized_path": str(normalized_path.relative_to(root)),
        "normalized_sha256": normalized_sha256,
        "insights": insights,
    }
    manifest_path = root / "data" / "manifests" / date_key / "matutina.json"
    write_json(manifest_path, manifest)
    diff_path = root / "data" / "diffs" / f"{date_key}.md"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_text = (
        f"# Monitor DOF — {publication_date.isoformat()}\n\n"
        "Sin publicaciones en el índice oficial para esta edición.\n"
        if status == "no_edition"
        else render_diff(publication_date, changes)
    )
    diff_path.write_text(diff_text, encoding="utf-8")
    state_path = root / "data" / "state" / "latest.json"
    write_json(
        state_path,
        {
            "status": status,
            "publication_date": date_key,
            "edition": EDITION,
            "normalized_sha256": normalized_sha256,
            "manifest_path": str(manifest_path.relative_to(root)),
            "updated_at": manifest["generated_at"],
        },
    )
    site_path = root / "site" / "index.html"
    site_path.parent.mkdir(parents=True, exist_ok=True)
    site_path.write_text(render_site(manifest, notes), encoding="utf-8")
    (site_path.parent / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    return MonitorResult(status, len(notes), index_url, normalized_sha256)


def parse_args() -> argparse.Namespace:
    """Parse the monitor command without coupling it to the comparison CLI."""

    parser = argparse.ArgumentParser(description="Captura y cataloga una edición oficial del DOF.")
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--root", type=Path, default=Path("."))
    return parser.parse_args()


def main() -> int:
    """Run the monitor from a scheduled workflow or manually."""

    args = parse_args()
    try:
        result = run_monitor(args.date, args.root.resolve())
    except (OSError, ValueError) as error:
        print(f"error: {error}")
        return 2
    print(
        json.dumps(
            {
                "status": result.status,
                "note_count": result.note_count,
                "index_url": result.index_url,
                "normalized_sha256": result.normalized_sha256,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
