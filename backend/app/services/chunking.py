from docling_core.types.doc.document import DoclingDocument, SectionHeaderItem, TextItem

from app.services.embeddings import tokenizer_and_limit

CHUNK_OVERLAP_TOKENS = 32
CHUNKING_VERSION = "section-token-offsets-v2"


def chunk_document(
    doc: DoclingDocument, *, tokenizer=None, model_limit: int | None = None,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[dict]:
    """Preserve source substrings; never decode token IDs back into source text."""
    if tokenizer is None and model_limit is None:
        tokenizer, model_limit = tokenizer_and_limit()
    if tokenizer is None or model_limit is None:
        raise ValueError("Supply both tokenizer and model_limit, or neither")
    if not getattr(tokenizer, "is_fast", False):
        raise ValueError("Chunking requires a fast tokenizer with character offsets")
    budget = model_limit - tokenizer.num_special_tokens_to_add(pair=False)
    if budget <= 0 or not 0 <= overlap_tokens < budget:
        raise ValueError("Token overlap must be nonnegative and smaller than the content budget")

    chunks = []
    section = "Untitled"
    items = []
    for item, _level in doc.iterate_items():
        if isinstance(item, SectionHeaderItem):
            chunks.extend(_split_section(items, section, tokenizer, model_limit, budget, overlap_tokens))
            items = []
            section = item.text
        elif isinstance(item, TextItem) and item.text.strip():
            pages = sorted({p.page_no for p in item.prov if p.page_no is not None})
            items.append((item.text, pages))
    chunks.extend(_split_section(items, section, tokenizer, model_limit, budget, overlap_tokens))
    return chunks


def _split_section(items, section, tokenizer, model_limit, budget, overlap):
    if not items:
        return []
    parts, provenance = [], []
    cursor = 0
    for text, pages in items:
        if parts:
            parts.append("\n")
            cursor += 1
        provenance.append((cursor, cursor + len(text), pages))
        parts.append(text)
        cursor += len(text)
    text = "".join(parts)
    offsets = tokenizer(text, add_special_tokens=False, truncation=False, return_offsets_mapping=True)["offset_mapping"]
    if not offsets:
        raise ValueError("Nonempty extracted text produced no embedding tokens")

    chunks = []
    start = 0
    while start < len(offsets):
        end = min(start + budget, len(offsets))
        char_start = 0 if start == 0 else offsets[start][0]
        # A substring cut within a word can tokenize differently. Recount the
        # exact emitted text, including special tokens, before accepting it.
        while end > start:
            char_end = offsets[end][0] if end < len(offsets) else len(text)
            value = text[char_start:char_end]
            count = len(tokenizer(value, add_special_tokens=True, truncation=False)["input_ids"])
            if value.strip() and count <= model_limit:
                break
            end -= 1
        if end == start:
            raise ValueError("Cannot split this text within the embedding model token limit")
        touched = [pages for left, right, pages in provenance if left < char_end and right > char_start]
        pages = sorted({page for group in touched for page in group})
        chunks.append({
            "text": value, "section": section,
            "page": pages[0] if pages else None,
            "pages": pages, "page_start": pages[0] if pages else None,
            "page_end": pages[-1] if pages else None,
            "provenance_complete": all(touched), "token_count": count,
        })
        if end == len(offsets):
            break
        start = max(start + 1, end - overlap)
    return chunks
