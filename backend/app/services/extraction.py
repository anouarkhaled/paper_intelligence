from docling.document_converter import DocumentConverter
from docling.exceptions import ConversionError
from docling_core.types.doc.document import DoclingDocument


class ExtractionError(Exception):
    """Raised when a PDF cannot be parsed into a structured document."""


def extract_pdf(file_path: str) -> DoclingDocument:
    converter = DocumentConverter()
    try:
        result = converter.convert(file_path)
    except ConversionError as e:
        raise ExtractionError(f"Could not extract text from PDF: {file_path}") from e

    return result.document
