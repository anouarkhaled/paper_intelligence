import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.schemas import UploadResponse
from app.services.chunking import chunk_document
from app.services.embeddings import embed_texts
from app.services.extraction import ExtractionError, extract_pdf
from app.services.vector_store import ensure_collection, upsert_chunks

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB, per docs/requirements.md NFR3

# In-memory registry: paper_id -> metadata. MVP limitation — no persistence
# layer yet, so this is lost on server restart (see docs/requirements.md
# open questions). Fine for a single-process learning project; would need
# a real database before any multi-instance or persistent deployment.
papers: dict[str, dict] = {}


@router.post("/papers/upload", response_model=UploadResponse)
async def upload_paper(file: UploadFile) -> UploadResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50MB limit")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        doc = extract_pdf(tmp_path)
    except ExtractionError:
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    chunks = chunk_document(doc)
    vectors = embed_texts([chunk["text"] for chunk in chunks])

    paper_id = str(uuid.uuid4())
    ensure_collection()
    upsert_chunks(paper_id, chunks, vectors)

    papers[paper_id] = {
        "filename": file.filename,
        "num_pages": len(doc.pages),
        "num_chunks": len(chunks),
    }

    return UploadResponse(paper_id=paper_id, **papers[paper_id])
