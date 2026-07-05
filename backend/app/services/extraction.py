from functools import lru_cache

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.exceptions import ConversionError
from docling_core.types.doc.document import DoclingDocument


class ExtractionError(Exception):
    """Raised when a PDF cannot be parsed into a structured document."""


@lru_cache
def _get_converter() -> DocumentConverter:
    # DocumentConverter() loads OCR sub-models (RapidOCR) on construction.
    # Creating a fresh one per call reloaded those models on every single
    # upload — measured at ~38s/request. Caching it turns that into a
    # one-time cost per server process instead of a per-request one.
    #
    # do_ocr=False: MVP scope explicitly excludes scanned/image-only PDFs
    # (see docs/requirements.md open questions). OCR is Docling's default
    # but its own docs note it "significantly increases processing time" —
    # skipping it is a large speedup for normal born-digital PDFs, which
    # already have an embedded text layer and don't need OCR at all.
    pipeline_options = PdfPipelineOptions(do_ocr=False)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )


def extract_pdf(file_path: str) -> DoclingDocument:
    try:
        result = _get_converter().convert(file_path)
    except ConversionError as e:
        raise ExtractionError(f"Could not extract text from PDF: {file_path}") from e

    return result.document
