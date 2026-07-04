from docling_core.types.doc.document import DoclingDocument, SectionHeaderItem, TextItem

CHUNK_SIZE_WORDS = 500
CHUNK_OVERLAP_WORDS = 50


def _make_chunk(words: list[str], section: str, page: int | None) -> dict:
    return {"text": " ".join(words), "section": section, "page": page}


def chunk_document(doc: DoclingDocument) -> list[dict]:
    chunks: list[dict] = []
    current_section = "Untitled"
    buffer_words: list[str] = []
    buffer_page: int | None = None

    for item, _level in doc.iterate_items():
        if isinstance(item, SectionHeaderItem):
            if buffer_words:
                chunks.append(_make_chunk(buffer_words, current_section, buffer_page))
            buffer_words = []
            buffer_page = None
            current_section = item.text
            continue

        if not isinstance(item, TextItem):
            continue

        page = item.prov[0].page_no if item.prov else None
        if buffer_page is None:
            buffer_page = page
        buffer_words.extend(item.text.split())

        if len(buffer_words) >= CHUNK_SIZE_WORDS:
            chunks.append(_make_chunk(buffer_words, current_section, buffer_page))
            buffer_words = buffer_words[-CHUNK_OVERLAP_WORDS:]
            buffer_page = page

    if buffer_words:
        chunks.append(_make_chunk(buffer_words, current_section, buffer_page))

    return chunks
