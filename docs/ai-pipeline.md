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
- **Chunk size:** ~500 tokens
- **Overlap:** ~50 tokens between consecutive chunks *within the same
  section*
- **Metadata per chunk:** `{ section: str, page: int }` at minimum —
  this is what makes citations (`docs/api-contract.md`) possible at all

**Why overlap matters:** without it, a sentence that's relevant to a
question could get cut in half across two chunks, and neither half alone
is a good match for the question's embedding. Overlap means the "seam"
between chunks isn't a hard cut — some context survives on both sides.

**Why chunk *within* sections, not across them:** a chunk that spans two
different sections would have ambiguous metadata (which section does it
belong to?) and would mix unrelated content, hurting both retrieval
precision and citation accuracy.

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

**top-k:** start with **k=5** retrieved chunks per question. At ~500
tokens each, 5 chunks is ~2500 tokens of context handed to the LLM
alongside the question — enough grounding without bloating the prompt or
the latency budget (NFR1: <5s).

---

*Revisit this doc after Phase 10 (evaluation) — if retrieval quality is
poor, this is the first place to look: chunk size, k, or embedding model
choice are the usual suspects before reaching for something more complex
like reranking or hybrid search.*
