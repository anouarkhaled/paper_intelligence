import pytest
from docling_core.types.doc.document import DoclingDocument

from app.services.extraction import ExtractionError, extract_pdf


def test_extract_pdf_returns_docling_document(sample_doc):
    assert isinstance(sample_doc, DoclingDocument)


def test_extract_pdf_raises_extraction_error_on_missing_file():
    with pytest.raises(ExtractionError):
        extract_pdf("this_file_does_not_exist.pdf")
