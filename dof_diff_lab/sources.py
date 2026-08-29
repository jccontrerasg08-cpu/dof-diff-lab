from __future__ import annotations

from datetime import date
import json
import time
from typing import Callable
from urllib.request import Request, urlopen

OFFICIAL_HOSTS = {"dof.gob.mx", "www.dof.gob.mx", "sidof.segob.gob.mx"}


def sidof_notes_url(publication_date: date) -> str:
    return f"https://sidof.segob.gob.mx/dof/sidof/notas/{publication_date:%d-%m-%Y}"


def sidof_note_api_url(code: str) -> str:
    return f"https://sidof.segob.gob.mx/dof/sidof/notas/nota/{code}"


def sidof_note_public_url(code: str, *, has_html: bool, has_image: bool) -> str:
    if has_html:
        return f"https://sidof.segob.gob.mx/notas/{code}"
    if has_image:
        return f"https://sidof.segob.gob.mx/notas/imagenes/{code}"
    return f"https://sidof.segob.gob.mx/notas/{code}"


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


def _flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {"s", "si", "sí", "true", "1", "y", "yes"}


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
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
        has_html = _flag(_first(raw, "existeHtml", "has_html"))
        has_document = _flag(_first(raw, "existeDoc", "has_document"))
        has_image = _flag(_first(raw, "existeImagen", "has_image"))
        journal_code = _first(raw, "codDiario", "journal_code")
        notes.append({
            "code": code,
            "title": title,
            "canonical_url": sidof_note_public_url(code, has_html=has_html, has_image=has_image),
            "source_api_url": sidof_note_api_url(code),
            "publication_date": publication_date.isoformat(),
            "edition": edition,
            "section": str(section).strip() if section else None,
            "issuer_primary": str(issuer_primary).strip() if issuer_primary else None,
            "issuer_secondary": str(issuer_secondary).strip() if issuer_secondary else None,
            "source_id": "sidof",
            "title_available": title_value not in (None, ""),
            "has_html": has_html,
            "has_document": has_document,
            "has_image": has_image,
            "page_start": _optional_int(_first(raw, "pagina", "page_start")),
            "page_end": _optional_int(_first(raw, "paginaHasta", "page_end")),
            "journal_code": str(journal_code).strip() if journal_code not in (None, "") else None,
        })
    return sorted(notes, key=lambda item: (str(item["edition"]), str(item["code"])))


def fetch_json(
    url: str,
    attempts: int = 3,
    opener: Callable[..., object] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> object:
    if attempts < 1:
        raise ValueError("attempts debe ser al menos 1")
    request = Request(
        url,
        headers={
            "User-Agent": "dof-diff-lab/1.1 (+https://github.com/jccontrerasg08-cpu/dof-diff-lab)",
            "Accept": "application/json",
        },
    )
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            with opener(request, timeout=30) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise ValueError(f"SIDOF respondió HTTP {status}")
                return json.loads(response.read().decode("utf-8"))
        except OSError as error:
            last_error = error
            if attempt + 1 < attempts:
                sleeper(float(2**attempt))
    raise OSError(f"No se pudo consultar SIDOF: {last_error}") from last_error


def fetch_sidof_notes(publication_date: date, fetcher: Callable[[str], object] = fetch_json) -> list[dict[str, object]]:
    return normalize_sidof_payload(fetcher(sidof_notes_url(publication_date)), publication_date)