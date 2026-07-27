"""
PDF report extraction pipeline: download -> text -> regex-first, AI-fallback.

Generalized from 901justice's parse_jail_pdf.py, which extracts structured
monthly metrics from the Shelby County Jail Report Card PDFs. The same pattern
applies to any recurring government PDF (budget documents, authorizer reports,
board packets):

    1. download_pdf()      cache the source PDF locally
    2. extract_text()      pull raw text with pymupdf
    3. extract_metrics()   run caller-supplied regex extractors, then fill the
                           gaps with AI extraction (toolkit.ai_extract) using a
                           field-description schema

Regex hits win over AI values for the fields they cover — deterministic
extraction is cheaper and auditable; the AI pass is the safety net for layout
drift and fields with no reliable anchor text.

Usage:
    from toolkit.pdf_report import download_pdf, extract_text, extract_metrics

    pdf = download_pdf(url, cache_dir)
    text = extract_text(pdf)
    values = extract_metrics(
        text,
        schema={"totalSeats": "Total funded pre-K seats countywide"},
        regex_extractors={"totalSeats": r"Total\\s+Seats\\D*([\\d,]+)"},
        context="Shelby County Pre-K annual report",
    )
"""

from __future__ import annotations

import re
from pathlib import Path

import requests


def download_pdf(url: str, cache_dir: Path, timeout: int = 30) -> Path:
    """Download a PDF to cache_dir (skipping if already cached); return its path."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    filepath = cache_dir / url.split("/")[-1]
    if filepath.exists():
        return filepath
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    filepath.write_bytes(r.content)
    return filepath


def extract_text(pdf_path: Path) -> str:
    """Extract full text from a PDF, page-tagged for AI context."""
    import fitz  # pymupdf

    doc = fitz.open(str(pdf_path))
    pages = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append(f"[PAGE {page_num + 1}]\n{text}")
    doc.close()
    return "\n\n".join(pages)


def first_number(text: str) -> float | None:
    """First numeric token in a string ('1,234' -> 1234, '31.5' -> 31.5)."""
    m = re.search(r"(?<!\d)(\d[\d,]*(?:\.\d+)?)(?!\d)", text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    return float(raw) if "." in raw else int(raw)


def apply_regex_extractors(text: str, extractors: dict[str, str]) -> dict:
    """
    Run {field: pattern} extractors against the text. Each pattern should have
    one capture group holding the numeric value; commas are stripped.
    """
    result: dict = {}
    for field, pattern in extractors.items():
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                result[field] = float(raw) if "." in raw else int(raw)
            except ValueError:
                result[field] = m.group(1)
    return result


def extract_metrics(
    text: str,
    schema: dict[str, str],
    regex_extractors: dict[str, str] | None = None,
    context: str = "Government report extraction",
    verbose: bool = True,
) -> dict:
    """
    Extract schema fields from report text. Regex extractors run first; AI
    extraction (if an API key is configured) fills fields regex didn't resolve.
    Fields missing from both come back as None.
    """
    regex_result = apply_regex_extractors(text, regex_extractors or {})

    remaining = {k: v for k, v in schema.items() if regex_result.get(k) is None}
    ai_result: dict = {}
    if remaining:
        try:
            from .ai_extract import extract_fields
        except ImportError:  # running as a loose script, not a package
            from ai_extract import extract_fields  # type: ignore
        ai_result = extract_fields(text=text, schema=remaining,
                                   context=context, verbose=verbose)

    return {
        field: regex_result.get(field, ai_result.get(field))
        for field in schema
    }
