from __future__ import annotations

from datetime import date
import json
from typing import Callable
from urllib.request import Request, urlopen

OFFICIAL_HOSTS = {"dof.gob.mx", "www.dof.gob.mx", "sidof.segob.gob.mx"}

SOURCE_REGISTRY: dict[str, dict[str, object]] = {
    "sidof": {
        "authority": "primary",
        "priority": 10,
        "base_url": "https://sidof.segob.gob.mx/dof/sidof",
        "format": "json",
        "capabilities": ["daily_notes", "note_detail", "editions"],
    },
    "dof_index": {
        "authority": "primary",
        "priority": 20,
        "base_url": "https://dof.gob.mx",
        "format": "html",
        "capabilities": ["daily_index", "note_links"],
    },
    "tavily": {
        "authority": "discovery_only",
        "priority": 100,
        "base_url": "https://api.tavily.com",
        "format": "json",
        "capabilities": ["search", "map", "extract"],
    },
}


def sidof_notes_url(publication_date: date) -> str:
    return f"https://sidof.segob.gob.mx/dof/sidof/notas/{publication_date:%d-%m-%Y}"


def sidof_note_url(code: str) -> str:
    return f"https://sidof.segob.gob.mx/dof/sidof/notas/nota/{code}"


def _edition_name(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"mat", "m", "matutina", "1"} or "matut" in text:
        return "matutina"
    if text in {"ves", "v", "vespertina", "2"} or "vespert" in text:
        return "vespertina"
    if text in {"ext", "e", "extraordinaria", "3"} or "extra" in text:
        return "extraordinaria"
    return text or "desconocida"


def _first(mapping: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _iter_daily_notes(payload: object) -> list[tuple[str, dict[str, object]]]:
    if isinstance(payload, list):
        return [("desconocida", item) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    grouped_keys = (
        ("matutina", "NotasMatutinas"),
        ("vespertina", "NotasVespertinas"),
        ("extraordinaria", "NotasExtraordinarias"),
    )
    grouped: list[tuple[str, dict[str, object]]] = []
    for edition, key in grouped_keys:
        value = payload.get(key)
        if isinstance(value, list):
            grouped.extend((edition, item) for item in value if isinstance(item, dict))
    if grouped or any(key in payload for _, key in grouped_keys):
        return grouped

    for key in ("Notas", "notas", "Nota", "nota"):
        value = payload.get(key)
        if isinstance(value, list):
            return [("desconocida", item) for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [("desconocida", value)]
    return []


def normalize_sidof_payload(payload: object, publication_date: date) -> list[dict[str, object]]:
    notes: list[dict[str, object]] = []
    for edition_from_group, raw in _iter_daily_notes(payload):
        code_value = _first(raw, "codNota", "codigo", "code")
        if code_value in (None, ""):
            continue
        code = str(code_value)
        title_value = _first(raw, "titulo", "title", "cadenaTitulo")
        title = str(title_value).strip() if title_value not in (None, "") else f"Nota DOF {code}"
        edition_value = _first(raw, "codEdicion", "edicion", "nombreEdicion")
        edition = _edition_name(edition_value) if edition_value else edition_from_group
        issuer_primary = _first(raw, "nombreCodOrgaUno", "codOrgaUno", "issuer_primary")
        issuer_secondary = _first(
            raw,
            "codOrgaDos",
            "nombreOrganismo",
            "nombOrganismo",
            "organismo",
            "dependencia",
            "emisor",
        )
        section = _first(raw, "codSeccion", "seccion", "section")
        notes.append({
            "code": code,
            "title": title,
            "canonical_url": sidof_note_url(code),
            "publication_date": publication_date.isoformat(),
            "edition": edition,
            "section": str(section).strip() if section else None,
            "issuer_primary": str(issuer_primary).strip() if issuer_primary else None,
            "issuer_secondary": str(issuer_secondary).strip() if issuer_secondary else None,
            "source_id": "sidof",
            "title_available": title_value not in (None, ""),
        })
    return sorted(notes, key=lambda item: (str(item["edition"]), str(item["code"])))


def fetch_json(url: str, opener: Callable[..., object] = urlopen) -> object:
    request = Request(
        url,
        headers={
            "User-Agent": "dof-diff-lab/1.1 (+https://github.com/jccontrerasg08-cpu/dof-diff-lab)",
            "Accept": "application/json",
        },
    )
    with opener(request, timeout=30) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise ValueError(f"SIDOF respondió HTTP {status}")
        body = response.read()
    return json.loads(body.decode("utf-8"))


def fetch_sidof_notes(publication_date: date, fetcher: Callable[[str], object] = fetch_json) -> list[dict[str, object]]:
    return normalize_sidof_payload(fetcher(sidof_notes_url(publication_date)), publication_date)
