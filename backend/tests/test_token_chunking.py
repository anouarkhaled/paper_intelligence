"""Offline tests: real Docling objects and a real fast WordPiece tokenizer."""
import importlib.util
import sys
from types import ModuleType

import pytest
from docling_core.types.doc.document import BoundingBox, DoclingDocument, DocItemLabel, ProvenanceItem
from tokenizers import Tokenizer
from tokenizers.models import WordPiece
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.processors import TemplateProcessing
from transformers import PreTrainedTokenizerFast
from app.settings import BACKEND_DIR


@pytest.fixture
def tokenizer():
    words = ['[UNK]', '[CLS]', '[SEP]', '[PAD]', 'alpha', 'beta', 'gamma', 'delta', 'micro', '##scope', 'café', ',', '!']
    backend = Tokenizer(WordPiece({word: i for i, word in enumerate(words)}, unk_token='[UNK]'))
    backend.pre_tokenizer = Whitespace()
    backend.post_processor = TemplateProcessing(single='[CLS] $A [SEP]', special_tokens=[('[CLS]', 1), ('[SEP]', 2)])
    return PreTrainedTokenizerFast(tokenizer_object=backend, unk_token='[UNK]', cls_token='[CLS]', sep_token='[SEP]', pad_token='[PAD]', model_max_length=256)


@pytest.fixture
def chunker(monkeypatch, tokenizer):
    embeddings = ModuleType('app.services.embeddings')
    embeddings.tokenizer_and_limit = lambda: (tokenizer, 256)
    monkeypatch.setitem(sys.modules, 'app.services.embeddings', embeddings)
    spec = importlib.util.spec_from_file_location('offline_chunking', BACKEND_DIR / 'app/services/chunking.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_text(doc, text, page=None):
    prov = None if page is None else ProvenanceItem(page_no=page, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, len(text)))
    return doc.add_text(label=DocItemLabel.TEXT, text=text, prov=prov)


def split(chunker, tokenizer, doc, overlap=2, limit=8):
    return chunker.chunk_document(doc, tokenizer=tokenizer, model_limit=limit, overlap_tokens=overlap)


def test_long_paragraph_is_bounded_including_special_tokens(chunker, tokenizer):
    doc = DoclingDocument(name='long')
    add_text(doc, 'microscope alpha beta café! ' * 50, 1)
    chunks = split(chunker, tokenizer, doc)
    assert len(chunks) > 10
    for chunk in chunks:
        count = len(tokenizer(chunk['text'], add_special_tokens=True, truncation=False)['input_ids'])
        assert chunk['token_count'] == count <= 8
        assert chunk['pages'] == [1]


def test_zero_overlap_preserves_exact_text_and_punctuation(chunker, tokenizer):
    doc = DoclingDocument(name='exact')
    text = '  alpha beta, café! microscope gamma delta ' * 20
    add_text(doc, text, 1)
    chunks = split(chunker, tokenizer, doc, overlap=0)
    assert ''.join(c['text'] for c in chunks) == text


def test_overlap_preserves_boundary_evidence(chunker, tokenizer):
    doc = DoclingDocument(name='overlap')
    add_text(doc, 'alpha beta gamma delta alpha beta gamma delta alpha beta', 1)
    chunks = split(chunker, tokenizer, doc)
    assert chunks[0]['text'].split()[-2:] == chunks[1]['text'].split()[:2]
    assert len(chunks) >= 2


def test_section_boundaries_do_not_share_overlap(chunker, tokenizer):
    doc = DoclingDocument(name='sections')
    doc.add_heading('First')
    add_text(doc, 'alpha beta', 1)
    doc.add_heading('Second')
    add_text(doc, 'gamma delta', 2)
    chunks = split(chunker, tokenizer, doc)
    assert [(c['section'], c['text'], c['pages']) for c in chunks] == [('First', 'alpha beta', [1]), ('Second', 'gamma delta', [2])]


def test_page_range_and_missing_provenance(chunker, tokenizer):
    doc = DoclingDocument(name='pages')
    add_text(doc, 'alpha', 1)
    add_text(doc, 'beta', 3)
    add_text(doc, 'gamma')
    chunk, = split(chunker, tokenizer, doc)
    assert chunk['pages'] == [1, 3]
    assert chunk['page_start'] == 1 and chunk['page_end'] == 3
    assert chunk['page'] == 1 and chunk['provenance_complete'] is False


def test_all_item_provenance_is_retained(chunker, tokenizer):
    doc = DoclingDocument(name='multi-page-item')
    item = add_text(doc, 'alpha beta', 2)
    item.prov.append(ProvenanceItem(page_no=4, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 10)))
    chunk, = split(chunker, tokenizer, doc)
    assert chunk['pages'] == [2, 4] and chunk['provenance_complete'] is True


def test_no_page_is_invented(chunker, tokenizer):
    doc = DoclingDocument(name='unknown')
    add_text(doc, 'alpha beta')
    chunk, = split(chunker, tokenizer, doc)
    assert chunk['page'] is None and chunk['pages'] == []
    assert chunk['page_start'] is None and chunk['page_end'] is None
    assert chunk['provenance_complete'] is False


@pytest.mark.parametrize('overlap,limit', [(-1, 8), (6, 8), (32, 2)])
def test_invalid_budget(chunker, tokenizer, overlap, limit):
    with pytest.raises(ValueError, match='overlap'):
        split(chunker, tokenizer, DoclingDocument(name='empty'), overlap, limit)


def test_empty_document_and_default_model_policy(chunker):
    doc = DoclingDocument(name='empty')
    assert chunker.chunk_document(doc) == []
    add_text(doc, 'alpha ' * 600, 1)
    assert all(c['token_count'] <= 256 for c in chunker.chunk_document(doc))


def test_slow_tokenizer_is_rejected(chunker):
    with pytest.raises(ValueError, match='fast tokenizer'):
        chunker.chunk_document(DoclingDocument(name='empty'), tokenizer=object(), model_limit=256)
