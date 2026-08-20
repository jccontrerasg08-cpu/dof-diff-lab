"""Generate a traceable local HTML diff for TXT or PDF documents."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import HtmlDiff
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Document:
    """A validated input document and the provenance needed for its report."""

    path: Path
    text: str
    digest: str
    source_type: str

    @property
    def line_count(self) -> int:
        return len(self.text.splitlines())


class PdfHasNoTextError(ValueError):
    """Raised when a PDF has no usable native text layer."""


def add_page_markers(text: str) -> str:
    """Expose Poppler page breaks as visible diff context."""

    pages = [page.strip() for page in text.split("\f") if page.strip()]
    return "\n".join(f"--- Página {number} ---\n{page}" for number, page in enumerate(pages, start=1))


def extract_pdf_text(path: Path) -> str:
    """Extract selectable text from one PDF with the local pdftotext utility."""

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise ValueError("No se encontró pdftotext; no es posible leer PDF localmente.") from error
    if result.returncode:
        detail = result.stderr.strip() or f"pdftotext terminó con código {result.returncode}"
        raise ValueError(f"No se pudo extraer texto del PDF {path.name}: {detail}")
    if not result.stdout.strip():
        raise PdfHasNoTextError(f"El PDF no contiene texto extraíble: {path.name}")
    return add_page_markers(result.stdout)


def extract_ocr_text(path: Path) -> str:
    """OCR a scanned PDF locally into a temporary derivative and extract its text."""

    try:
        with TemporaryDirectory(prefix="dof-diff-lab-") as directory:
            derived = Path(directory) / "ocr.pdf"
            result = subprocess.run(
                [
                    "ocrmypdf",
                    "--language",
                    "spa",
                    "--rotate-pages",
                    "--deskew",
                    "--output-type",
                    "pdf",
                    str(path),
                    str(derived),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            if result.returncode:
                detail = result.stderr.strip() or f"ocrmypdf terminó con código {result.returncode}"
                raise ValueError(f"No se pudo aplicar OCR local a {path.name}: {detail}")
            return extract_pdf_text(derived)
    except FileNotFoundError as error:
        raise ValueError("No se encontró ocrmypdf; no es posible aplicar OCR localmente.") from error
    except PdfHasNoTextError as error:
        raise ValueError(f"El OCR no produjo texto extraíble: {path.name}") from error


def read_document(value: str, use_ocr: bool) -> Document:
    """Read a non-empty TXT or PDF, using OCR only when explicitly requested."""

    path = Path(value)
    if not path.is_file():
        raise ValueError(f"La entrada debe ser un archivo existente: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            text = extract_pdf_text(path)
            source_type = "PDF"
        except PdfHasNoTextError:
            if not use_ocr:
                raise
            text = extract_ocr_text(path)
            source_type = "PDF_OCR"
    elif suffix == ".txt":
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"La entrada debe estar codificada como UTF-8: {path}") from error
        source_type = "TXT"
    else:
        raise ValueError(f"La entrada debe terminar en .txt o .pdf: {path}")
    if not text.strip():
        raise ValueError(f"La entrada no puede estar vacía: {path}")
    return Document(
        path=path,
        text=text,
        digest=sha256(path.read_bytes()).hexdigest(),
        source_type=source_type,
    )


def validate_source_urls(values: list[str]) -> tuple[str | None, str | None]:
    """Validate two optional, user-supplied government HTTPS source URLs locally."""

    if not values:
        return None, None
    if len(values) != 2:
        raise ValueError("--source-url debe proporcionarse exactamente dos veces.")
    for value in values:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username
            or parsed.password
            or not (host == "gob.mx" or host.endswith(".gob.mx"))
        ):
            raise ValueError("--source-url debe ser una URL HTTPS de un dominio gob.mx sin credenciales.")
    return values[0], values[1]


def document_metadata(document: Document, source_url: str | None) -> dict[str, str | int]:
    """Return provenance that can be persisted without document content."""

    metadata: dict[str, str | int] = {
        "file": document.path.name,
        "type": document.source_type,
        "sha256": document.digest,
        "line_count": document.line_count,
    }
    if source_url:
        metadata["source_url"] = source_url
    return metadata


def write_manifest(
    path: Path,
    before: Document,
    after: Document,
    report: Path,
    source_urls: tuple[str | None, str | None],
) -> None:
    """Write a content-free JSON record for a completed comparison."""

    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "report": report.name,
        "inputs": {
            "before": document_metadata(before, source_urls[0]),
            "after": document_metadata(after, source_urls[1]),
        },
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_result(
    path: Path,
    before: Document,
    after: Document,
    report: Path,
    manifest: Path | None,
    source_urls: tuple[str | None, str | None],
) -> None:
    """Write a stable, content-free completion record for local automation."""

    record: dict[str, object] = {
        "status": "report_created",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "report": report.name,
        "inputs": {
            "before": document_metadata(before, source_urls[0]),
            "after": document_metadata(after, source_urls[1]),
        },
    }
    if manifest:
        record["manifest"] = manifest.name
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def provenance_row(label: str, document: Document) -> str:
    """Return escaped HTML for one input document's provenance."""

    return (
        "<tr>"
        f"<th>{escape(label)}</th>"
        f"<td>{escape(document.path.name)}</td>"
        f"<td>{escape(document.source_type)}</td>"
        f"<td><code>{document.digest}</code></td>"
        f"<td>{document.line_count}</td>"
        "</tr>"
    )


def build_report(before: Document, after: Document) -> str:
    """Build a self-contained comparison report without external resources."""

    # ponytail: las filas normativas largas desbordan horizontalmente; envolverlas
    # recursivamente falla con documentos reales. Un normalizador de tablas solo se
    # justificará si el scroll horizontal impide la revisión manual.
    table = HtmlDiff(wrapcolumn=None).make_table(
        before.text.splitlines(),
        after.text.splitlines(),
        fromdesc=escape(before.path.name),
        todesc=escape(after.path.name),
        context=True,
        numlines=3,
    )
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    metadata = "\n".join(
        (
            "<section>",
            "<h1>DOF Diff Lab</h1>",
            "<p>Comparación local, educativa y trazable; no interpreta vigencia ni obligaciones.</p>",
            "<table><thead><tr><th>Documento</th><th>Archivo</th><th>Tipo</th><th>SHA-256</th>"
            "<th>Líneas</th></tr></thead><tbody>",
            provenance_row("Antes", before),
            provenance_row("Después", after),
            "</tbody></table>",
            f"<p>Generado: <time>{escape(created_at)}</time></p>",
            "</section>",
        )
    )
    style = (
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.5}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #bbb;"
        "padding:.45rem;text-align:left;vertical-align:top}code{overflow-wrap:anywhere}"
        "table.diff{font-family:ui-monospace,monospace;font-size:.85rem}</style>"
    )
    return "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">" + style + "</head><body>" + metadata + table + "</body></html>\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara dos TXT UTF-8 o PDF con texto extraíble y genera un informe HTML local."
    )
    parser.add_argument("before", help="archivo anterior .txt UTF-8 o .pdf")
    parser.add_argument("after", help="archivo posterior .txt UTF-8 o .pdf")
    parser.add_argument("--output", "-o", required=True, help="ruta del informe HTML")
    parser.add_argument(
        "--manifest",
        help="ruta opcional para un manifiesto JSON sin contenido de entrada",
    )
    parser.add_argument(
        "--result-json",
        help="ruta opcional para un resultado JSON estable y sin contenido de entrada",
    )
    parser.add_argument(
        "--source-url",
        action="append",
        metavar="URL",
        help="URL HTTPS gob.mx de origen; úsese dos veces, primero antes y después",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="aplica OCR local en español solo a PDFs sin texto extraíble",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        before = read_document(args.before, args.ocr)
        after = read_document(args.after, args.ocr)
        output = Path(args.output)
        manifest = Path(args.manifest) if args.manifest else None
        result_json = Path(args.result_json) if args.result_json else None
        source_urls = validate_source_urls(args.source_url or [])
        input_paths = {before.path.resolve(), after.path.resolve()}
        output_paths = [output, *(path for path in (manifest, result_json) if path)]
        if output.resolve() in input_paths:
            raise ValueError("La salida debe ser distinta de las entradas.")
        if manifest and manifest.resolve() in input_paths:
            raise ValueError("El manifiesto debe ser distinto de las entradas y el informe.")
        if result_json and result_json.resolve() in input_paths:
            raise ValueError("El resultado JSON debe ser distinto de las entradas.")
        if manifest and manifest.resolve() == output.resolve():
            raise ValueError("El manifiesto debe ser distinto del informe.")
        if result_json and result_json.resolve() in {output.resolve(), *(path.resolve() for path in (manifest,) if path)}:
            raise ValueError("El resultado JSON debe ser distinto del informe y el manifiesto.")
        if output.exists():
            raise ValueError("El informe ya existe; use una ruta nueva para no sobrescribir evidencia.")
        if manifest and manifest.exists():
            raise ValueError("El manifiesto ya existe; use una ruta nueva para no sobrescribir evidencia.")
        if result_json and result_json.exists():
            raise ValueError("El resultado JSON ya existe; use una ruta nueva para no sobrescribir evidencia.")
        if before.text == after.text:
            raise ValueError("Las entradas son idénticas; no hay cambios que comparar.")
        for path in output_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        if result_json:
            write_result(result_json, before, after, output, manifest, source_urls)
        if manifest:
            write_manifest(manifest, before, after, output, source_urls)
        output.write_text(build_report(before, after), encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Informe creado: {Path(args.output)}")
    if args.manifest:
        print(f"Manifiesto creado: {Path(args.manifest)}")
    if args.result_json:
        print(f"Resultado JSON creado: {Path(args.result_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
