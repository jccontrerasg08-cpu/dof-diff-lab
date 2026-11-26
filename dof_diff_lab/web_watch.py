"""Independent, evidence-only monitoring of official trade-information pages.

This watcher records hashes, official links and listing changes. It never
changes the normalized DOF catalogs or infers legal effect.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from typing import Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)
import xml.etree.ElementTree as ET

from .monitor import canonical_bytes, folded_text, normalized_text

SCHEMA_VERSION = "1.0"
PARSER_VERSION = "1.0"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
OFFICIAL_DOMAINS = (
    "anam.gob.mx",
    "dof.gob.mx",
    "segob.gob.mx",
    "sat.gob.mx",
    "snice.gob.mx",
    "ventanillaunica.gob.mx",
)
_SOURCE_ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


@dataclass(frozen=True)
class WatchSource:
    source_id: str
    title: str
    url: str
    format: Literal["html", "rss", "pdf"]
    coverage_note: str
    include_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceResponse:
    status: int
    content_type: str
    charset: str | None
    final_url: str
    body: bytes


@dataclass(frozen=True)
class WatchResult:
    source_id: str
    status: str
    content_sha256: str
    record_count: int
    diff_path: str | None


class SourceError(ValueError):
    """A source response could not be safely interpreted as evidence."""


class _OfficialRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> Request | None:
        try:
            parts = urlsplit(new_url)
        except ValueError as exc:
            raise SourceError("HTTP redirect points to an invalid URL") from exc
        if (
            parts.scheme.lower() != "https"
            or _canonical_official_url(new_url, request.full_url) is None
        ):
            raise SourceError("HTTP redirect points to a non-official or insecure URL")
        return super().redirect_request(
            request, file, code, message, headers, new_url
        )


SOURCES = (
    WatchSource(
        "snice-home",
        "SNICE: Actualidad y avisos",
        "https://www.snice.gob.mx/cs/avi/snice/home.html",
        "html",
        "Página oficial de novedades; el cambio requiere revisión humana.",
    ),
    WatchSource(
        "snice-dof-history",
        "SNICE: Histórico de publicaciones del DOF",
        "https://www.snice.gob.mx/cs/avi/snice/historicos.dof.html",
        "html",
        "Índice secundario de publicaciones; el DOF sigue siendo la fuente primaria.",
    ),
    WatchSource(
        "snice-legal-library",
        "SNICE: Biblioteca jurídica",
        "https://www.snice.gob.mx/cs/avi/snice/biblioteca.juridica.html",
        "html",
        "Biblioteca oficial; sus enlaces identifican documentos, no vigencia legal.",
    ),
    WatchSource(
        "snice-nontariff-notices",
        "SNICE: Avisos y permisos",
        "https://www.snice.gob.mx/cs/avi/snice/drrnas.avisosypermisos.html",
        "html",
        "Avisos y permisos de comercio exterior publicados por SNICE.",
    ),
    WatchSource(
        "anam-feed",
        "ANAM: feed oficial",
        "https://www.anam.gob.mx/feed/",
        "rss",
        "El feed existe, pero estaba vacío al verificarlo; no cubre por sí solo criterios SAT.",
    ),
    WatchSource(
        "sat-current-regulations-index",
        "SAT: índice anual de normatividad RMF/RGCE",
        "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/",
        "html",
        "El índice oficial usa una redirección meta-refresh a la página anual vigente.",
        (
            "reglas generales de comercio exterior",
            "rgce",
            "clasificacion arancelaria",
            "nico",
        ),
    ),
    WatchSource(
        "sat-rgce-2026",
        "SAT: Reglas Generales de Comercio Exterior 2026",
        "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rgce/rgce/ReglasGeneralesComercioExteriorpara2026.pdf",
        "pdf",
        "PDF oficial; se conserva URL y hash, no se interpreta ni republica su contenido.",
    ),
    WatchSource(
        "sat-rgce-2026-second-modification",
        "SAT: compilación de la segunda modificación RGCE 2026",
        "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rmf/compiladas/Compilado2daRMRGCEpara2026.pdf",
        "pdf",
        "Documento oficial verificado; una URL fija no garantiza que liste futuras resoluciones.",
    ),
    WatchSource(
        "sat-annex-22-2026",
        "SAT: Anexo 22 RGCE 2026",
        "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rgce/compiladas/CompiladoAnexo22_1raRMRGCE2026.pdf",
        "pdf",
        "Anexo 22 oficial; cambios en catálogos deben validarse contra su publicación oficial.",
    ),
    WatchSource(
        "vucem-home",
        "VUCEM: avisos visibles en el portal",
        "https://www.ventanillaunica.gob.mx/vucem/",
        "html",
        "Monitorea cambios de la portada; no se confirmó un catálogo público estable de Anexo 22.",
    ),
)


def _official_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_DOMAINS)


def _canonical_official_url(url: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, url.strip())
    try:
        parts = urlsplit(absolute)
        port = parts.port
    except ValueError:
        return None
    valid_port = (
        port in (None, 80) if parts.scheme.lower() == "http" else port in (None, 443)
    )
    if (
        parts.scheme.lower() not in ("http", "https")
        or not _official_host(parts.hostname)
        or parts.username is not None
        or parts.password is not None
        or not valid_port
    ):
        return None
    hostname = parts.hostname.lower()
    return urlunsplit(("https", hostname, parts.path or "/", parts.query, ""))


def _official_https_url(url: str) -> str | None:
    try:
        parts = urlsplit(url)
    except (TypeError, ValueError):
        return None
    if parts.scheme.lower() != "https":
        return None
    return _canonical_official_url(url, url)


def _validate_source(source: WatchSource) -> str:
    if (
        not isinstance(source.source_id, str)
        or not _SOURCE_ID_PATTERN.fullmatch(source.source_id)
    ):
        raise SourceError("source id must contain lowercase letters, digits and hyphens")
    if source.format not in ("html", "rss", "pdf"):
        raise SourceError(f"unsupported source format: {source.format}")
    source_url = _official_https_url(source.url)
    if source_url is None:
        raise SourceError("source URL must use HTTPS and an official host")
    return source_url


class _MetaRefreshParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.target: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attributes = dict(attrs)
        if (attributes.get("http-equiv") or "").lower() != "refresh":
            return
        content = attributes.get("content") or ""
        _delay, separator, directive = content.partition(";")
        key, equals, target = directive.partition("=")
        if not separator or not equals or key.strip().lower() != "url":
            return
        self.target = target.strip().strip("\"'")


def _fetch_url(
    url: str,
    *,
    timeout: int,
    attempts: int,
    opener: Callable[..., object] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> SourceResponse:
    request_url = _official_https_url(url)
    if request_url is None:
        raise SourceError("request URL must use HTTPS and an official host")
    request = Request(
        request_url,
        headers={
            "Accept": "text/html, application/rss+xml, application/xml, application/pdf",
            "User-Agent": "dof-diff-lab-web-watch/1.0 (+https://github.com/)",
        },
    )
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            if opener is None:
                response_opener = build_opener(_OfficialRedirectHandler()).open
            else:
                response_opener = opener
            with response_opener(request, timeout=timeout) as response:
                final_url = response.geturl()
                status = response.status
                content_type = response.headers.get_content_type().lower()
                charset = response.headers.get_content_charset()
                body = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except HTTPError as exc:
            if exc.code not in (408, 425, 429) and not 500 <= exc.code <= 599:
                status = exc.code
                exc.close()
                raise SourceError(f"request failed with HTTP {status}") from exc
            last_error = exc
            exc.close()
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt + 1 < attempts:
            sleeper(float(2**attempt))
    else:
        raise SourceError(f"request failed after {attempts} attempts: {last_error}") from last_error

    if status != 200:
        raise SourceError(f"unexpected HTTP status {status}")
    try:
        final_parts = urlsplit(final_url)
    except ValueError as exc:
        raise SourceError("invalid final response URL") from exc
    if _official_https_url(final_url) is None:
        raise SourceError(f"redirected to a non-official URL: {final_url}")
    if len(body) > MAX_RESPONSE_BYTES:
        raise SourceError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
    return SourceResponse(status, content_type, charset, final_url, body)


def fetch_source(
    source: WatchSource,
    *,
    timeout: int = 30,
    attempts: int = 3,
    opener: Callable[..., object] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> SourceResponse:
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120:
        raise ValueError("timeout must be an integer in 1..120")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 5:
        raise ValueError("attempts must be an integer in 1..5")
    current_url = _validate_source(source)
    visited: set[str] = set()
    for _redirect_number in range(4):
        if current_url in visited:
            raise SourceError(f"meta-refresh loop detected at {current_url}")
        visited.add(current_url)
        response = _fetch_url(
            current_url,
            timeout=timeout,
            attempts=attempts,
            opener=opener,
            sleeper=sleeper,
        )
        if response.content_type not in ("text/html", "application/xhtml+xml"):
            return response
        try:
            document = response.body.decode(response.charset or "utf-8-sig")
        except (LookupError, UnicodeDecodeError) as exc:
            raise SourceError(f"could not decode HTML response: {exc}") from exc
        refresh_parser = _MetaRefreshParser()
        refresh_parser.feed(document)
        if not refresh_parser.target:
            return response
        target_url = _canonical_official_url(refresh_parser.target, response.final_url)
        if not target_url:
            raise SourceError("meta refresh points to a non-official or invalid URL")
        current_url = target_url
    raise SourceError("too many official meta-refresh redirects")


class _PageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text: list[str] = []
        self.links: list[dict[str, str]] = []
        self.rejected_links = 0
        self._hidden_depth = 0
        self._href: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._hidden_depth += 1
        if tag == "a" and self._hidden_depth == 0:
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            title = normalized_text(" ".join(self._anchor_text))
            url = _canonical_official_url(self._href, self.base_url)
            if title and url:
                self.links.append({"title": title, "url": url})
            elif title:
                self.rejected_links += 1
            self._href = None
            self._anchor_text = []
        if tag in ("script", "style", "noscript") and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth:
            return
        text = normalized_text(data)
        if text:
            self.text.append(text)
        if self._href is not None:
            self._anchor_text.append(data)


def _unique_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    by_url: dict[str, dict[str, str]] = {}
    for record in records:
        url = record.get("url")
        title = record.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not title:
            raise SourceError("source entry is missing a title or official URL")
        previous = by_url.get(url)
        if previous is None:
            by_url[url] = record
        elif previous != record:
            if set(previous) != {"title", "url"} or set(record) != {"title", "url"}:
                raise SourceError(f"conflicting entries for the same URL: {url}")
            by_url[url] = max((previous, record), key=lambda item: (len(item["title"]), item["title"]))
    return sorted(by_url.values(), key=lambda item: (item["url"], item["title"]))


def _html_content(source: WatchSource, response: SourceResponse) -> dict[str, object]:
    if response.content_type not in ("text/html", "application/xhtml+xml"):
        raise SourceError(f"expected HTML, received {response.content_type!r}")
    try:
        document = response.body.decode(response.charset or "utf-8-sig")
    except (LookupError, UnicodeDecodeError) as exc:
        raise SourceError(f"could not decode HTML response: {exc}") from exc
    parser = _PageParser(response.final_url)
    parser.feed(document)
    all_page_text = normalized_text(" ".join(parser.text))
    if len(all_page_text) < 50:
        raise SourceError("HTML page has too little visible text to verify its structure")
    if source.include_keywords:
        keywords = tuple(folded_text(keyword) for keyword in source.include_keywords)
        records = _unique_records(
            [
                record
                for record in parser.links
                if any(keyword in folded_text(record["title"]) for keyword in keywords)
            ]
        )
        page_text = normalized_text(
            " ".join(f"{record['title']} {record['url']}" for record in records)
        )
    else:
        records = _unique_records(parser.links)
        page_text = all_page_text
    return {
        "records": records,
        "visible_text_sha256": sha256(page_text.encode("utf-8")).hexdigest(),
        "rejected_links": parser.rejected_links,
    }


def _xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return normalized_text(" ".join(element.itertext()))


def _rss_content(response: SourceResponse) -> dict[str, object]:
    if response.content_type not in ("application/rss+xml", "application/xml", "text/xml"):
        raise SourceError(f"expected RSS/XML, received {response.content_type!r}")
    upper_body = response.body.upper()
    if b"<!DOCTYPE" in upper_body or b"<!ENTITY" in upper_body:
        raise SourceError("RSS/XML document types and entities are not accepted")
    try:
        root = ET.fromstring(response.body)
    except ET.ParseError as exc:
        raise SourceError(f"invalid RSS/XML: {exc}") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "rss":
        raise SourceError("expected an RSS 2.0 feed")
    channel = next(
        (child for child in root if child.tag.rsplit("}", 1)[-1].lower() == "channel"),
        None,
    )
    if channel is None:
        raise SourceError("RSS channel is missing")

    records: list[dict[str, str]] = []
    rejected_links = 0
    for item in channel:
        if item.tag.rsplit("}", 1)[-1].lower() != "item":
            continue
        title = _xml_text(next((node for node in item if node.tag.rsplit("}", 1)[-1].lower() == "title"), None))
        raw_url = _xml_text(next((node for node in item if node.tag.rsplit("}", 1)[-1].lower() == "link"), None))
        url = _canonical_official_url(raw_url, response.final_url) if raw_url else None
        if not title:
            raise SourceError("RSS item is missing its title")
        if not url:
            rejected_links += 1
            continue
        description = _xml_text(
            next(
                (node for node in item if node.tag.rsplit("}", 1)[-1].lower() == "description"),
                None,
            )
        )
        published = _xml_text(
            next(
                (node for node in item if node.tag.rsplit("}", 1)[-1].lower() == "pubdate"),
                None,
            )
        )
        record = {"title": title, "url": url}
        if description:
            record["summary"] = description
        if published:
            record["published_at"] = published
        records.append(record)

    channel_title = _xml_text(next((node for node in channel if node.tag.rsplit("}", 1)[-1].lower() == "title"), None))
    description = _xml_text(
        next((node for node in channel if node.tag.rsplit("}", 1)[-1].lower() == "description"), None)
    )
    return {
        "records": _unique_records(records),
        "channel_title": channel_title,
        "channel_description": description,
        "rejected_links": rejected_links,
    }


def parse_response(source: WatchSource, response: SourceResponse) -> dict[str, object]:
    """Parse only a source's declared format and preserve official evidence links."""
    source_url = _validate_source(source)
    if response.status != 200:
        raise SourceError(f"unexpected HTTP status {response.status}")
    if _official_https_url(response.final_url) is None:
        raise SourceError(f"non-official or invalid final response URL: {response.final_url}")
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise SourceError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")

    if source.format == "html":
        parsed = _html_content(source, response)
    elif source.format == "rss":
        parsed = _rss_content(response)
    elif source.format == "pdf":
        if response.content_type not in ("application/pdf", "application/octet-stream"):
            raise SourceError(f"expected PDF, received {response.content_type!r}")
        if not response.body.startswith(b"%PDF-"):
            raise SourceError("response does not have a PDF signature")
        parsed = {
            "records": [{"title": source.title, "url": source_url}],
            "document_sha256": sha256(response.body).hexdigest(),
            "document_bytes": len(response.body),
            "rejected_links": 0,
        }
    else:
        raise SourceError(f"unsupported source format: {source.format}")

    if source.format == "pdf":
        parsed["content_sha256"] = parsed["document_sha256"]
    else:
        content = {
            key: value
            for key, value in parsed.items()
            if key not in ("document_sha256", "document_bytes")
        }
        parsed["content_sha256"] = sha256(canonical_bytes(content)).hexdigest()
    return parsed


def _index_records(records: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("url"), str)
            or not isinstance(record.get("title"), str)
        ):
            raise SourceError("invalid record in source snapshot")
        identity = record["url"]
        if identity in indexed:
            raise SourceError(f"duplicate record identity: {identity}")
        indexed[identity] = record
    return indexed


def _record_changes(
    previous: list[dict[str, str]], current: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, object]]]:
    old_records = _index_records(previous)
    new_records = _index_records(current)
    added = [new_records[key] for key in sorted(new_records.keys() - old_records.keys())]
    removed = [old_records[key] for key in sorted(old_records.keys() - new_records.keys())]
    modified = [
        {"before": old_records[key], "after": new_records[key]}
        for key in sorted(old_records.keys() & new_records.keys())
        if old_records[key] != new_records[key]
    ]
    return added, removed, modified


def _read_snapshot(
    path: Path, source: WatchSource, source_url: str
) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"could not read prior snapshot {path}: {exc}") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("source_id") != source.source_id
        or payload.get("url") != source_url
        or not isinstance(payload.get("records"), list)
        or not isinstance(payload.get("content_sha256"), str)
    ):
        raise SourceError(f"invalid prior snapshot: {path}")
    return payload


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        temporary_path.write_bytes(canonical_bytes(value))
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _store_result(
    root: Path,
    source: WatchSource,
    parsed: dict[str, object],
    *,
    now: datetime,
) -> WatchResult:
    source_url = _validate_source(source)
    snapshot_path = root / "data" / "web-watch" / "snapshots" / f"{source.source_id}.json"
    previous = _read_snapshot(snapshot_path, source, source_url)
    previous_hash = previous.get("content_sha256") if previous else None
    current_hash = parsed["content_sha256"]
    records = parsed["records"]
    if not isinstance(records, list):
        raise SourceError(f"invalid parsed record list for {source.source_id}")

    if previous is not None and previous_hash == current_hash:
        return WatchResult(
            source.source_id, "unchanged", str(current_hash), len(records), None
        )

    observed_at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    snapshot: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "source_id": source.source_id,
        "title": source.title,
        "url": source_url,
        "format": source.format,
        "coverage_note": source.coverage_note,
        "content_sha256": current_hash,
        "first_seen_at": previous.get("first_seen_at", observed_at) if previous else observed_at,
        "last_changed_at": observed_at,
        "record_count": len(records),
        "records": records,
        "rejected_links": parsed.get("rejected_links", 0),
    }
    for optional_key in (
        "visible_text_sha256",
        "document_sha256",
        "document_bytes",
        "channel_title",
        "channel_description",
    ):
        if optional_key in parsed:
            snapshot[optional_key] = parsed[optional_key]
    diff_path: str | None = None
    status = "baseline_created"
    if previous is not None:
        old_records = previous.get("records")
        if not isinstance(old_records, list):
            raise SourceError(f"invalid records in prior snapshot: {snapshot_path}")
        added, removed, modified = _record_changes(old_records, records)
        status = "changed"
        event = {
            "schema_version": SCHEMA_VERSION,
            "source_id": source.source_id,
            "title": source.title,
            "url": source_url,
            "detected_at": observed_at,
            "previous_content_sha256": previous_hash,
            "content_sha256": current_hash,
            "visible_text_changed": previous.get("visible_text_sha256") != parsed.get("visible_text_sha256"),
            "rejected_links_before": previous.get("rejected_links", 0),
            "rejected_links_after": parsed.get("rejected_links", 0),
            "metadata_changes": {
                key: {"before": previous.get(key), "after": parsed.get(key)}
                for key in ("channel_title", "channel_description")
                if previous.get(key) != parsed.get(key)
            },
            "added": added,
            "removed": removed,
            "modified": modified,
            "coverage_note": source.coverage_note,
        }
        transition = sha256(
            canonical_bytes(
                {
                    "source_id": source.source_id,
                    "previous": previous_hash,
                    "current": current_hash,
                }
            )
        ).hexdigest()[:20]
        event_path = (
            root
            / "data"
            / "web-watch"
            / "diffs"
            / source.source_id
            / f"{transition}.json"
        )
        if event_path.exists():
            try:
                existing_event = json.loads(event_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SourceError(f"could not read prior diff {event_path}: {exc}") from exc
            comparable_event = dict(event)
            existing_comparable = dict(existing_event) if isinstance(existing_event, dict) else {}
            comparable_event.pop("detected_at", None)
            existing_comparable.pop("detected_at", None)
            if existing_comparable != comparable_event:
                raise SourceError(f"conflicting diff already exists: {event_path}")
        else:
            _write_json(event_path, event)
        diff_path = event_path.relative_to(root).as_posix()

    _write_json(snapshot_path, snapshot)
    return WatchResult(source.source_id, status, str(current_hash), len(records), diff_path)


def run_watch(
    root: Path,
    *,
    sources: tuple[WatchSource, ...] = SOURCES,
    fetcher: Callable[..., SourceResponse] = fetch_source,
    timeout: int = 30,
    now: datetime | None = None,
) -> list[WatchResult]:
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120:
        raise ValueError("timeout must be an integer in 1..120")
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    results: list[WatchResult] = []
    failures: list[str] = []
    for source in sources:
        try:
            _validate_source(source)
            response = fetcher(source, timeout=timeout)
            parsed = parse_response(source, response)
            result = _store_result(Path(root), source, parsed, now=observed_at)
        except SourceError as exc:
            failures.append(f"{source.source_id}: {exc}")
        else:
            results.append(result)
    if failures:
        successful = "\n".join(
            f"{result.source_id}: {result.status}; sha256={result.content_sha256}"
            for result in results
        )
        message = "one or more sources failed:\n" + "\n".join(failures)
        if successful:
            message += "\nSuccessful sources:\n" + successful
        raise SourceError(message)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor official trade-information sources.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        results = run_watch(args.root, timeout=args.timeout)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for result in results:
        print(
            f"{result.source_id}: {result.status}; "
            f"{result.record_count} records; sha256={result.content_sha256}"
            + (f"; diff={result.diff_path}" if result.diff_path else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
