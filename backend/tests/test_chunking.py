from app.services.chunking import chunk_document


def test_chunk_document_returns_chunks_with_expected_keys(sample_doc):
    chunks = chunk_document(sample_doc)

    assert len(chunks) > 0
    for chunk in chunks:
        assert set(chunk.keys()) == {"text", "section", "page"}
        assert isinstance(chunk["text"], str) and chunk["text"]
        assert isinstance(chunk["section"], str)
        assert isinstance(chunk["page"], int)


def test_chunk_document_produces_reasonable_chunk_count(sample_doc):
    chunks = chunk_document(sample_doc)

    # This paper produced 29 chunks when the chunking strategy was verified
    # (docs/ai-pipeline.md). A wide range here catches gross regressions
    # (e.g. chunking breaking entirely) without being brittle to small
    # algorithm tweaks.
    assert 10 <= len(chunks) <= 100


def test_chunk_document_captures_known_section(sample_doc):
    chunks = chunk_document(sample_doc)
    sections = {chunk["section"] for chunk in chunks}

    assert "3.5 Positional Encoding" in sections
