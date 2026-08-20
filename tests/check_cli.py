"""Small runnable checks for the first DOF Diff Lab prototype."""

from __future__ import annotations

from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zlib


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "dof_diff_lab", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def make_pdf(path: Path, text: str) -> None:
    """Create a minimal text PDF without third-party libraries."""

    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET\n".encode("ascii")
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
    )
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    pdf.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(pdf)



def make_scanned_pdf(path: Path, text: str) -> None:
    """Create a synthetic raster-only PDF for the OCR path without external content."""

    glyphs = {
        "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
        "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
        "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    }
    scale, spacing, height = 12, 2, 7
    width = sum(5 + spacing for _ in text) * scale
    pixels = bytearray([255]) * (width * height * scale)
    cursor = 0
    for character in text:
        for row, pattern in enumerate(glyphs[character]):
            for column, bit in enumerate(pattern):
                if bit == "1":
                    for y in range(row * scale, (row + 1) * scale):
                        start = y * width + (cursor + column) * scale
                        pixels[start : start + scale] = b"\x00" * scale
        cursor += 5 + spacing
    image = zlib.compress(bytes(pixels))
    content = f"q {width} 0 0 {height * scale} 0 0 cm /Im0 Do Q\n".encode("ascii")
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /XObject << /Im0 4 0 R >> >> /MediaBox [0 0 "
        + f"{width} {height * scale}".encode("ascii")
        + b"] /Contents 5 0 R >>",
        b"<< /Type /XObject /Subtype /Image /Width "
        + str(width).encode("ascii")
        + b" /Height "
        + str(height * scale).encode("ascii")
        + b" /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length "
        + str(len(image)).encode("ascii")
        + b" >>\nstream\n"
        + image
        + b"\nendstream",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
    )
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    pdf.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(pdf)


def make_multi_page_pdf(path: Path, *pages: str) -> None:
    """Combine minimal text PDFs with Poppler for page-marker coverage."""

    page_paths = [path.with_name(f"{path.stem}-{number}.pdf") for number in range(1, len(pages) + 1)]
    for page_path, text in zip(page_paths, pages, strict=True):
        make_pdf(page_path, text)
    merge = subprocess.run(
        ["pdfunite", *(str(page_path) for page_path in page_paths), str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert merge.returncode == 0, merge.stderr


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        before = workspace / "antes.txt"
        after = workspace / "despues.txt"
        report = workspace / "informe.html"
        manifest = workspace / "evidencia.json"
        result_json = workspace / "resultado.json"
        before.write_text("Artículo 1\nTasa 10%\n", encoding="utf-8")
        after.write_text("Artículo 1\nTasa 15%\n", encoding="utf-8")

        before_url = "https://dof.gob.mx/nota_detalle.php?codigo=5698661&fecha=15/08/2023"
        after_url = "https://dof.gob.mx/nota_detalle.php?codigo=5724207&fecha=22/04/2024"
        result = run(
            str(before),
            str(after),
            "--output",
            str(report),
            "--manifest",
            str(manifest),
            "--result-json",
            str(result_json),
            "--source-url",
            before_url,
            "--source-url",
            after_url,
        )
        assert result.returncode == 0, result.stderr
        content = report.read_text(encoding="utf-8")
        assert "DOF Diff Lab" in content
        assert sha256(before.read_bytes()).hexdigest() in content
        assert sha256(after.read_bytes()).hexdigest() in content
        visible = re.sub(r"<[^>]+>", "", content)
        assert "Tasa" in visible and "15%" in visible
        evidence = json.loads(manifest.read_text(encoding="utf-8"))
        assert evidence["generated_at"]
        assert evidence["report"] == report.name
        assert evidence["inputs"]["before"] == {
            "file": before.name,
            "type": "TXT",
            "sha256": sha256(before.read_bytes()).hexdigest(),
            "line_count": 2,
            "source_url": before_url,
        }
        assert evidence["inputs"]["after"]["sha256"] == sha256(after.read_bytes()).hexdigest()
        assert evidence["inputs"]["after"]["source_url"] == after_url
        assert "Artículo" not in manifest.read_text(encoding="utf-8")
        result_record = json.loads(result_json.read_text(encoding="utf-8"))
        assert result_record["status"] == "report_created"
        assert result_record["report"] == report.name
        assert result_record["manifest"] == manifest.name
        assert result_record["inputs"] == evidence["inputs"]
        assert "Artículo" not in result_json.read_text(encoding="utf-8")

        blocked_parent = workspace / "no-es-directorio"
        blocked_parent.write_text("archivo", encoding="utf-8")
        blocked_report = workspace / "informe-bloqueado.html"
        blocked_manifest = blocked_parent / "evidencia.json"
        blocked = run(
            str(before), str(after), "--output", str(blocked_report), "--manifest", str(blocked_manifest)
        )
        assert blocked.returncode == 2
        assert not blocked_report.exists()

        blocked_result_report = workspace / "informe-result-bloqueado.html"
        blocked_result_manifest = workspace / "evidencia-result-bloqueada.json"
        blocked_result = run(
            str(before),
            str(after),
            "--output",
            str(blocked_result_report),
            "--manifest",
            str(blocked_result_manifest),
            "--result-json",
            str(blocked_parent / "resultado.json"),
        )
        assert blocked_result.returncode == 2
        assert not blocked_result_report.exists()
        assert not blocked_result_manifest.exists()

        one_url_output = workspace / "one-url.html"
        one_url = run(
            str(before), str(after), "--output", str(one_url_output), "--source-url", before_url
        )
        assert one_url.returncode == 2
        assert "exactamente dos veces" in one_url.stderr
        assert not one_url_output.exists()

        external_output = workspace / "external-url.html"
        external = run(
            str(before),
            str(after),
            "--output",
            str(external_output),
            "--source-url",
            "https://example.com/source",
            "--source-url",
            after_url,
        )
        assert external.returncode == 2
        assert "gob.mx" in external.stderr
        assert not external_output.exists()

        existing_report = workspace / "evidencia-previa.html"
        existing_report.write_text("informe anterior", encoding="utf-8")
        new_manifest = workspace / "nuevo-manifiesto.json"
        existing_report_result = run(
            str(before), str(after), "--output", str(existing_report), "--manifest", str(new_manifest)
        )
        assert existing_report_result.returncode == 2
        assert "informe ya existe" in existing_report_result.stderr
        assert existing_report.read_text(encoding="utf-8") == "informe anterior"
        assert not new_manifest.exists()

        existing_manifest = workspace / "evidencia-previa.json"
        existing_manifest.write_text("manifiesto anterior", encoding="utf-8")
        new_report = workspace / "nuevo-informe.html"
        existing_manifest_result = run(
            str(before), str(after), "--output", str(new_report), "--manifest", str(existing_manifest)
        )
        assert existing_manifest_result.returncode == 2
        assert "manifiesto ya existe" in existing_manifest_result.stderr
        assert existing_manifest.read_text(encoding="utf-8") == "manifiesto anterior"
        assert not new_report.exists()

        existing_result = workspace / "resultado-previo.json"
        existing_result.write_text("resultado anterior", encoding="utf-8")
        result_collision_report = workspace / "informe-result-collision.html"
        result_collision_manifest = workspace / "evidencia-result-collision.json"
        existing_result_run = run(
            str(before),
            str(after),
            "--output",
            str(result_collision_report),
            "--manifest",
            str(result_collision_manifest),
            "--result-json",
            str(existing_result),
        )
        assert existing_result_run.returncode == 2
        assert "resultado JSON ya existe" in existing_result_run.stderr
        assert existing_result.read_text(encoding="utf-8") == "resultado anterior"
        assert not result_collision_report.exists()
        assert not result_collision_manifest.exists()

        original_before = before.read_text(encoding="utf-8")
        output_collision = run(str(before), str(after), "--output", str(before))
        assert output_collision.returncode == 2
        assert "salida" in output_collision.stderr
        assert before.read_text(encoding="utf-8") == original_before

        manifest_collision = run(
            str(before), str(after), "--output", str(workspace / "other.html"), "--manifest", str(before)
        )
        assert manifest_collision.returncode == 2
        assert "manifiesto" in manifest_collision.stderr
        assert before.read_text(encoding="utf-8") == original_before

        result_input_collision = run(
            str(before), str(after), "--output", str(workspace / "other-result.html"), "--result-json", str(before)
        )
        assert result_input_collision.returncode == 2
        assert "resultado JSON" in result_input_collision.stderr
        assert before.read_text(encoding="utf-8") == original_before

        same_target = workspace / "misma-ruta.html"
        colliding = run(str(before), str(after), "--output", str(same_target), "--manifest", str(same_target))
        assert colliding.returncode == 2
        assert "manifiesto" in colliding.stderr

        long_before = workspace / "tabla-antes.txt"
        long_after = workspace / "tabla-despues.txt"
        long_report = workspace / "tabla.html"
        long_before.write_text("| " + "campo " * 400 + "|\n", encoding="utf-8")
        long_after.write_text("| " + "campo " * 399 + "cambio |\n", encoding="utf-8")
        long_result = run(str(long_before), str(long_after), "--output", str(long_report))
        assert long_result.returncode == 0, long_result.stderr
        assert long_report.exists()

        assert shutil.which("pdftotext"), "pdftotext debe estar disponible para procesar PDFs"
        assert shutil.which("pdfunite"), "pdfunite debe estar disponible para crear la prueba multipágina"
        before_pdf = workspace / "antes.pdf"
        after_pdf = workspace / "despues.pdf"
        pdf_report = workspace / "informe-pdf.html"
        make_pdf(before_pdf, "Tasa 10%")
        make_pdf(after_pdf, "Tasa 15%")
        pdf_result = run(str(before_pdf), str(after_pdf), "--output", str(pdf_report))
        assert pdf_result.returncode == 0, pdf_result.stderr
        pdf_content = pdf_report.read_text(encoding="utf-8")
        assert "PDF" in pdf_content
        assert sha256(before_pdf.read_bytes()).hexdigest() in pdf_content
        assert sha256(after_pdf.read_bytes()).hexdigest() in pdf_content

        before_pages = workspace / "antes-multipagina.pdf"
        after_pages = workspace / "despues-multipagina.pdf"
        page_report = workspace / "informe-multipagina.html"
        make_multi_page_pdf(before_pages, "Articulo 1", "Articulo 2\nTasa 10%")
        make_multi_page_pdf(after_pages, "Articulo 1", "Articulo 2\nTasa 15%")
        page_result = run(str(before_pages), str(after_pages), "--output", str(page_report))
        assert page_result.returncode == 0, page_result.stderr
        page_content = page_report.read_text(encoding="utf-8")
        page_visible = unescape(re.sub(r"<[^>]+>", "", page_content)).replace("\xa0", " ")
        assert "Página 2" in page_visible
        assert "15%" in page_visible

        scanned_pdf = workspace / "escaneado-sintetico.pdf"
        scanned_report = workspace / "informe-ocr.html"
        scanned_manifest = workspace / "evidencia-ocr.json"
        make_scanned_pdf(scanned_pdf, "TASATASATASATASA")
        assert not (ROOT / "tests" / "fixtures" / "escaneado.pdf").exists()
        scanned_without_ocr = run(str(scanned_pdf), str(after_pdf), "--output", str(scanned_report))
        assert scanned_without_ocr.returncode == 2
        assert "no contiene texto extraíble" in scanned_without_ocr.stderr
        assert not scanned_report.exists()

        scanned_with_ocr = run(
            str(scanned_pdf),
            str(after_pdf),
            "--output",
            str(scanned_report),
            "--manifest",
            str(scanned_manifest),
            "--ocr",
        )
        assert scanned_with_ocr.returncode == 0, scanned_with_ocr.stderr
        scanned_content = scanned_report.read_text(encoding="utf-8")
        assert "PDF_OCR" in scanned_content
        scanned_evidence = json.loads(scanned_manifest.read_text(encoding="utf-8"))
        assert scanned_evidence["inputs"]["before"]["type"] == "PDF_OCR"
        assert scanned_evidence["inputs"]["after"]["type"] == "PDF"
        assert sha256(scanned_pdf.read_bytes()).hexdigest() in scanned_content

        unsupported = workspace / "nota.md"
        unsupported.write_text("Documento no admitido", encoding="utf-8")
        unsupported_result = run(str(unsupported), str(after), "--output", str(workspace / "bad.html"))
        assert unsupported_result.returncode == 2
        assert ".txt o .pdf" in unsupported_result.stderr

        identical = run(str(before), str(before), "--output", str(workspace / "same.html"))
        assert identical.returncode == 2
        assert "idénticas" in identical.stderr


if __name__ == "__main__":
    main()
