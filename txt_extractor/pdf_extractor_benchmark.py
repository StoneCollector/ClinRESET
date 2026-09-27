import argparse
import importlib.util
import sys
import time
from pathlib import Path


def installed(name):
    return importlib.util.find_spec(name) is not None


def pypdfium2_extract(path):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(path))
    out = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            tp = page.get_textpage()
            try:
                text = tp.get_text_range()
            finally:
                tp.close()
                page.close()
            out.append(f"--- PAGE {i+1} ---\n{text.strip()}")
    finally:
        doc.close()
    return "\n\n".join(out)


def pypdf_extract(path):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n\n".join(
        f"--- PAGE {i+1} ---\n{(p.extract_text() or '').strip()}"
        for i, p in enumerate(reader.pages)
    )


def pdfplumber_extract(path):
    import pdfplumber
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            parts = [f"--- PAGE {i} ---", (page.extract_text() or "").strip()]
            try:
                tables = page.extract_tables()
                for j, table in enumerate(tables or [], 1):
                    parts.append(f"\n[TABLE {j}]")
                    for row in table:
                        parts.append(" | ".join("" if c is None else str(c).strip() for c in row))
            except Exception as e:
                parts.append(f"\n[TABLE EXTRACTION ERROR: {e}]")
            pages.append("\n".join(x for x in parts if x))
    return "\n\n".join(pages)


def pymupdf4llm_extract(path):
    import pymupdf4llm
    return pymupdf4llm.to_markdown(str(path))


def unstructured_extract(path):
    from unstructured.partition.pdf import partition_pdf
    elements = partition_pdf(filename=str(path))
    out = []
    for i, e in enumerate(elements, 1):
        text = str(e).strip()
        if text:
            category = getattr(e, "category", e.__class__.__name__)
            out.append(f"[{i}] {category}\n{text}")
    return "\n\n".join(out)


def marker_extract(path):
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(str(path))
    text, _, _ = text_from_rendered(rendered)
    return text


def textract_extract(path):
    import textract
    result = textract.process(str(path))
    return result.decode("utf-8", errors="replace") if isinstance(result, bytes) else str(result)


METHODS = {
    "pypdfium2": ("pypdfium2", pypdfium2_extract),
    "pypdf": ("pypdf", pypdf_extract),
    "pdfplumber": ("pdfplumber", pdfplumber_extract),
    "pymupdf4llm": ("pymupdf4llm", pymupdf4llm_extract),
    "unstructured": ("unstructured", unstructured_extract),
    "marker-pdf": ("marker", marker_extract),
    "textract": ("textract", textract_extract),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        print(f"Invalid PDF: {pdf}")
        return 1

    outdir = (args.output_dir or pdf.parent / "extraction_benchmark").resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    summary = [
        "PDF EXTRACTION BENCHMARK",
        "=" * 80,
        f"Input: {pdf}",
        "",
        "Methodology | Status | Time(s) | Characters | Output",
        "-" * 80,
    ]

    for name, (package, func) in METHODS.items():
        outfile = outdir / f"{pdf.stem}_{name.replace('-', '_')}.txt"
        print(f"[{name}]")

        if not installed(package):
            text = f"LIBRARY NOT INSTALLED\nRequired package: {package}"
            outfile.write_text(text, encoding="utf-8")
            summary.append(f"{name} | SKIPPED | - | 0 | {outfile.name}")
            print(f"  SKIPPED: install {package}")
            continue

        start = time.perf_counter()
        try:
            text = str(func(pdf) or "")
            elapsed = time.perf_counter() - start
            outfile.write_text(text, encoding="utf-8")
            summary.append(f"{name} | OK | {elapsed:.3f} | {len(text):,} | {outfile.name}")
            print(f"  OK: {elapsed:.3f}s, {len(text):,} chars")
        except Exception as e:
            elapsed = time.perf_counter() - start
            text = (
                f"EXTRACTION FAILED\n\n"
                f"Methodology: {name}\n"
                f"Exception: {type(e).__name__}: {e}\n"
            )
            outfile.write_text(text, encoding="utf-8")
            summary.append(f"{name} | FAILED | {elapsed:.3f} | 0 | {outfile.name}")
            print(f"  FAILED: {type(e).__name__}: {e}")

    summary_file = outdir / f"{pdf.stem}_benchmark_summary.txt"
    summary_file.write_text("\n".join(summary), encoding="utf-8")
    print(f"\nResults: {outdir}")
    print(f"Summary: {summary_file}")


if __name__ == "__main__":
    sys.exit(main())
