"""
main.py — CLI entry point for the ClinRESET extraction layer.

Usage
-----

Extract a medical PDF:
    python main.py extract path/to/report.pdf [--output output/] [--debug]

Run the benchmark (research only; does NOT affect production pipeline):
    python main.py benchmark path/to/report.pdf [--output-dir benchmark_results/]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Suppress verbose third-party output in normal mode.
    if not debug:
        for noisy in ("pymupdf", "pymupdf4llm", "fitz", "PIL"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# extract command
# ---------------------------------------------------------------------------


def cmd_extract(args: argparse.Namespace) -> int:
    """Run the production extraction pipeline on a PDF."""
    from extraction.pipeline import extract_document

    pdf_path = Path(args.pdf)
    output_root = Path(args.output)

    if not pdf_path.exists():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        return 1

    print(f"Extracting: {pdf_path}")

    result = extract_document(pdf_path, output_root=output_root, save_output=True)

    # ---- Concise summary ----
    print()
    print("=" * 50)
    print("  Extraction completed")
    print("=" * 50)
    print(f"  File:        {result.document.file_name}")
    print(f"  Source type: {result.document.source_type}")
    print(f"  Extractor:   {result.document.extractor}")
    print(f"  Pages:       {result.document.page_count}")
    print(f"  Sections:    {len(result.sections)}")
    print(f"  Tables:      {len(result.tables)}")
    print(f"  Measurements:{len(result.measurements)}")
    print(f"  Validation:  {result.validation.status}")
    if result.classification is not None:
        c = result.classification
        print(f"  Report type: {c.report_type} (status={c.status}, confidence={c.confidence:.2f})")
    if result.clinical_information is not None:
        ci = result.clinical_information
        print(f"  Clinical:    {len(ci.findings)} findings, {len(ci.anatomy)} anatomy, {len(ci.relationships)} relations, {len(ci.measurements)} measurements")
    print(f"  Output:      {output_root / pdf_path.stem}/")

    if result.validation.warnings:
        print()
        print("  Warnings:")
        for w in result.validation.warnings:
            print(f"    • {w}")

    if result.measurements:
        print()
        print("  Measurements extracted:")
        for m in result.measurements:
            unit = f" {m.unit}" if m.unit else ""
            ref = f"  [{m.reference_range}]" if m.reference_range else ""
            print(f"    • {m.name}: {m.value}{unit}{ref}")

    print("=" * 50)

    return 0 if result.validation.status != "FAILED" else 2


# ---------------------------------------------------------------------------
# benchmark command
# ---------------------------------------------------------------------------


def cmd_benchmark(args: argparse.Namespace) -> int:
    """
    Run multiple extractors and compare their output.

    This is a RESEARCH-ONLY command.  Its results do NOT influence the
    production extraction order, which is fixed.
    """
    import importlib.util
    import time

    pdf = Path(args.pdf).resolve()
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        print(f"Error: invalid PDF: {pdf}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else pdf.parent / "benchmark_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nBENCHMARK (research only) — {pdf.name}")
    print("=" * 70)
    print("NOTE: Benchmark results do NOT change the production extractor order.")
    print("=" * 70)

    # Import the existing benchmark helpers if available.
    bench_script = Path(__file__).parent / "txt_extractor" / "pdf_extractor_benchmark.py"

    if bench_script.exists():
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("pdf_extractor_benchmark", bench_script)
        bench_mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(bench_mod)

        # Delegate to the existing benchmark implementation.
        # Override sys.argv so the benchmark script parses correctly.
        import sys as _sys
        old_argv = _sys.argv
        _sys.argv = ["pdf_extractor_benchmark.py", str(pdf), "--output-dir", str(output_dir)]
        try:
            bench_mod.main()
        finally:
            _sys.argv = old_argv
    else:
        # Minimal inline benchmark using only the two production extractors.
        from extraction.extractors.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
        from extraction.extractors.coordinate_extractor import CoordinateExtractor

        extractors = [
            ("pymupdf4llm (production primary)", PyMuPDF4LLMExtractor(pdf)),
            ("coordinate (production fallback)", CoordinateExtractor(pdf)),
        ]

        for label, extractor in extractors:
            t0 = time.perf_counter()
            res = extractor.extract()
            elapsed = time.perf_counter() - t0
            text = res.get("markdown") or res.get("text") or ""
            status = "OK" if res["success"] else "FAILED"
            print(f"  {label:45s} {status:6s}  {elapsed:.3f}s  {len(text):,} chars")

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ClinRESET — Medical PDF extraction layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable DEBUG logging",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    p_extract = sub.add_parser("extract", help="Extract a medical PDF")
    p_extract.add_argument("pdf", help="Path to the PDF file")
    p_extract.add_argument(
        "--output",
        default="output",
        help="Output root directory (default: output/)",
    )

    # benchmark
    p_bench = sub.add_parser(
        "benchmark",
        help="Research benchmark — compare multiple extractors (does not change production order)",
    )
    p_bench.add_argument("pdf", help="Path to the PDF file")
    p_bench.add_argument("--output-dir", default=None, help="Benchmark output directory")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    _configure_logging(debug=args.debug)

    if args.command == "extract":
        return cmd_extract(args)
    elif args.command == "benchmark":
        return cmd_benchmark(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
