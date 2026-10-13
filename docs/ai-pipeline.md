# AI Pipeline Design

Decided before implementation (Phase 7), so Phase 8 is just "build what's
written here," not "figure it out while coding."

## Ingestion pipeline (Step 14)

```
Upload PDF
   |
Docling extraction   -> structured doc (sections, headings, page numbers)
   |
Chunking              -> list of {text, section, page} chunks
   |
Embedding             -> one vector per chunk
   |
Vector store (Qdrant) -> (vector, {text, section, page, paper_id}) upserted
```

Each stage takes the previous stage's output as its only input — no stage
reaches back into raw PDF bytes or an earlier stage's intermediate state.
This is what makes each stage independently testable (e.g. you can unit
test chunking with a hardcoded structured doc, without needing a real PDF
or a running vector DB).

## Chunking strategy (Step 15)

**Approach:** section-based chunking with overlap, not naive fixed-size
splitting of raw text.

**Why naive chunking is bad here specifically:** splitting a paper into
flat 500-character blocks ignores structure — a chunk could start
mid-sentence, span from the end of "Related Work" into the start of
"Methodology," or split a table from its caption. For a *research paper*
assistant, section boundaries carry meaning (a question about "the
methodology" should retrieve Methodology-section chunks, not an arbitrary
slice of the document).

**Decided parameters:**
- **Chunk size:** bounded by the loaded embedding model's effective input limit,
  including special tokens. Use the smaller finite limit declared by the model
  and tokenizer. MiniLM's commonly configured 256-token limit must be confirmed
  against the loaded artifact; it is not hardcoded here.
- **Overlap:** target 32 source tokens within the same section. Small windows
  reduced by retokenization may have less overlap to ensure forward progress.
- **Metadata:** section, exact known pages, page bounds, provenance completeness,
  and total token count. The legacy `page` field is the first known page or null.

Implementation uses a fast tokenizer's character offsets to slice original
text, preserving punctuation and accents. Each exact substring is retokenized
with special tokens and shortened until it fits. Embedding rejects over-budget
inputs rather than silently truncating. Slow tokenizers without offsets are
unsupported. Table/figure items remain outside this text-item chunker.

Page attribution is conservative: every provenance page of an overlapping
Docling text item is retained. A chunk may include only part of a multi-page
item, so these are possible source pages, not precise per-character citations.
Missing item provenance is represented explicitly and is never inferred from
an adjacent item. No claim-level citation validation is implemented yet.

The v2 chunking fingerprint invalidates prior word-based ingestions: re-upload
old documents. Dependency/model revisions remain unpinned, so the fingerprint
does not yet provide full artifact reproducibility.

**Why overlap matters:** without it, a sentence that's relevant to a
question could get cut in half across two chunks, and neither half alone
is a good match for the question's embedding. Overlap means the "seam"
between chunks isn't a hard cut — some context survives on both sides.

**Why chunk *within* sections, not across them:** a chunk that spans two
different sections would have ambiguous metadata (which section does it
belong to?) and would mix unrelated content, hurting both retrieval
precision and citation accuracy.

**Implementation note — considered and rejected markdown-based chunking:**
an alternative would be exporting via `doc.export_to_markdown()` and
splitting with LangChain's `MarkdownHeaderTextSplitter` +
`RecursiveCharacterTextSplitter`. Rejected because markdown export doesn't
carry page numbers directly — only a `page_break_placeholder` option that
would require counting placeholder occurrences to reconstruct page
numbers — and it needs two chained splitters instead of one pass.
Iterating `doc.iterate_items()` directly gives `page_no` and
`SectionHeaderItem` boundaries natively, so that's what's implemented in
`backend/app/services/chunking.py`.

## Embedding model

**Decided:** `sentence-transformers/all-MiniLM-L6-v2`

- ~80MB, runs fast on CPU (no GPU required) — matters because this is a
  learning project running locally, not a production deployment with GPU
  infrastructure.
- Produces 384-dimensional vectors — small enough that Qdrant similarity
  search stays fast even as chunks accumulate across many papers.
- Well-known default for RAG tutorials/projects, meaning debugging help
  and reference implementations are easy to find if something looks wrong.
- Trade-off: lower semantic precision than larger models (e.g.
  `all-mpnet-base-v2`). Acceptable for MVP; revisit only if retrieval
  quality evaluation (Phase 10) shows it's the bottleneck.

## Retrieval strategy (Step 16)

**Decided for MVP: pure semantic search.** Given a question, embed it with
the same model used for chunks, then ask Qdrant for the top-k most similar
chunk vectors.

**Explicitly NOT doing for MVP (and why):**
- **Hybrid search** (semantic + keyword/BM25): adds real value when exact
  terms matter (e.g. matching a specific dataset name or acronym exactly),
  but adds complexity (fusing two ranked lists) that isn't justified until
  evaluation (Phase 10) shows pure semantic search actually missing things.
- **Reranker**: a second model that re-scores the top-k results for
  precision. Worth adding once you have an evaluation set to *measure*
  whether it helps — adding it now would be optimizing blind.

**top-k:** currently **k=5**. The embedding tokenizer controls chunk size; the
generation model has a different tokenizer/context limit. Total generation
prompt budgeting and the <5s latency target require separate implementation
and measurement; neither is established by this chunking change.

---

*Revisit this doc after Phase 10 (evaluation) — if retrieval quality is
poor, this is the first place to look: chunk size, k, or embedding model
choice are the usual suspects before reaching for something more complex
like reranking or hybrid search.*
