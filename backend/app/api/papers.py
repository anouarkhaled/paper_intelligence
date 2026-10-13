import hashlib
import sqlite3
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.dependencies import LOCAL_OWNER_ID, get_document_store
from app.models.schemas import UploadResponse
from app.services.chunking import chunk_document
from app.services.document_store import Document, DocumentStore
from app.services.embeddings import embed_texts
from app.services.extraction import ExtractionError, extract_pdf
from app.services.ingestion_identity import pipeline_version
from app.services.vector_store import ensure_collection, upsert_chunks
from app.settings import get_settings

router = APIRouter()
INGESTION_LOCK = threading.Lock()


def _upload_response(document: Document) -> UploadResponse:
    return UploadResponse(
        paper_id=document.document_id, filename=document.filename,
        num_pages=document.num_pages, num_chunks=document.num_chunks,
    )


def _ingest(contents: bytes, filename: str, store: DocumentStore) -> UploadResponse:
    # The cached Docling converter has not been verified for concurrent use.
    # Keep one ingestion per process while freeing the API event loop.
    if not INGESTION_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Another document is being processed; try again later")
    try:
        return _process_upload(contents, filename, store)
    finally:
        INGESTION_LOCK.release()


def _process_upload(contents: bytes, filename: str, store: DocumentStore) -> UploadResponse:
    paper_id = str(uuid.uuid4())
    checksum = hashlib.sha256(contents).hexdigest()
    version = pipeline_version()
    try:
        store.create(
            document_id=paper_id, owner_id=LOCAL_OWNER_ID, filename=filename,
            source_checksum=checksum, pipeline_version=version,
        )
    except sqlite3.IntegrityError:
        existing = store.find_ingestion(
            owner_id=LOCAL_OWNER_ID, source_checksum=checksum, pipeline_version=version,
        )
        if existing is None:
            raise
        if existing.status == "ready":
            return _upload_response(existing)
        raise HTTPException(
            status_code=409,
            detail=f"This document ingestion is {existing.status}; automatic retry is not supported yet",
        ) from None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(contents)
        doc = extract_pdf(str(tmp_path))
        chunks = chunk_document(doc)
        if not doc.pages or not chunks:
            raise ExtractionError("PDF contains no usable pages or text chunks")
        vectors = embed_texts([chunk["text"] for chunk in chunks])
        if len(vectors) != len(chunks):
            raise ValueError("Embedding count does not match chunk count")
        ensure_collection()
        upsert_chunks(paper_id, chunks, vectors)
        return _upload_response(store.mark_ready(
            paper_id, owner_id=LOCAL_OWNER_ID,
            num_pages=len(doc.pages), num_chunks=len(chunks),
        ))
    except ExtractionError:
        store.mark_failed(paper_id, owner_id=LOCAL_OWNER_ID, failure_code="extraction_failed")
        raise HTTPException(status_code=422, detail="Could not extract text from PDF") from None
    except Exception:
        store.mark_failed(paper_id, owner_id=LOCAL_OWNER_ID, failure_code="ingestion_failed")
        raise HTTPException(status_code=503, detail="Document ingestion failed") from None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


@router.post("/papers/upload", response_model=UploadResponse)
async def upload_paper(
    file: UploadFile, store: DocumentStore = Depends(get_document_store),
) -> UploadResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read()
    settings = get_settings()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb}MB limit")
    if not contents:
        raise HTTPException(status_code=422, detail="PDF file is empty")

    try:
        return await run_in_threadpool(_ingest, contents, file.filename or "document.pdf", store)
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="Document metadata store is unavailable") from None
