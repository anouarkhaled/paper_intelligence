# Milestones & Tasks

Mirror this in GitHub Issues/Milestones (Repo -> Issues -> Milestones -> New milestone).
Each task below should become one GitHub Issue assigned to its milestone.
Keep tasks small and concrete — avoid vague ones like "work on backend".

## Milestone 1 — Project setup
- [x] Freeze scope (docs/requirements.md)
- [x] Freeze architecture/stack (docs/architecture.md)
- [x] Init repo, push to GitHub
- [ ] Create Python venv in backend/, verify `python --version` (3.11+)
- [ ] Install base backend deps (fastapi, uvicorn, langchain, docling, qdrant-client, sentence-transformers)
- [ ] Scaffold FastAPI app with a working `/health` endpoint
- [ ] Init frontend with React + Tailwind, verify dev server runs

## Milestone 2 — Document extraction
- [ ] Install Docling, run it on one sample PDF via a throwaway script
- [ ] Inspect Docling output structure (what fields does it give you?)
- [ ] Write `services/extraction.py`: PDF bytes -> structured doc
- [ ] Decide + implement chunking strategy (section-based, with overlap)
- [ ] Attach metadata to each chunk (`section`, `page`)
- [ ] Export chunks to JSON for one sample paper, manually inspect quality

## Milestone 3 — Embeddings + vector DB
- [ ] Run Qdrant locally (Docker)
- [ ] Pick a Sentence Transformers model, embed one chunk, check vector shape
- [ ] Write `services/embeddings.py`: chunks -> vectors
- [ ] Create Qdrant collection, upsert chunks + metadata for one paper
- [ ] Run a manual similarity search query, verify top-k results make sense

## Milestone 4 — RAG chatbot
- [ ] Define `POST /papers/upload` contract + implementation
- [ ] Define `POST /chat` contract + implementation
- [ ] Wire retriever: question -> embed -> top-k chunks
- [ ] Build prompt template that forces citation of section/page
- [ ] Call LLM, return answer + citations
- [ ] Manually test with 3-5 real questions against a real paper

## Milestone 5 — Frontend integration
- [ ] Upload page: PDF upload -> calls `/papers/upload`
- [ ] Chat page: question input -> calls `/chat`, renders answer + citations
- [ ] Paper viewer: preview PDF alongside chat
- [ ] End-to-end manual test: upload -> ask -> get cited answer
