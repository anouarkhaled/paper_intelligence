from pathlib import Path

import pytest

from app.services.extraction import extract_pdf

SAMPLE_PDF = Path(__file__).parent.parent.parent / "datasets" / "attention_is_all_you_need.pdf"


@pytest.fixture(scope="session")
def sample_pdf_path() -> Path:
    return SAMPLE_PDF


@pytest.fixture(scope="session")
def sample_doc(sample_pdf_path):
    """Extracted once per test session — Docling parsing takes a few seconds."""
    return extract_pdf(str(sample_pdf_path))
