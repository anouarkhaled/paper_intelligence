import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import LOCAL_OWNER_ID, get_document_store
from app.models.schemas import ChatRequest, ChatResponse
from app.models.errors import EmbeddingInputTooLongError
from app.rag.generation import generate_answer
from app.rag.retriever import retrieve_chunks
from app.services.document_store import DocumentNotFoundError, DocumentStore
from app.services.ingestion_identity import pipeline_version

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, store: DocumentStore = Depends(get_document_store)) -> ChatResponse:
    try:
        document = store.get(request.paper_id, owner_id=LOCAL_OWNER_ID)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="Document metadata store is unavailable") from None
    if document.status != "ready":
        raise HTTPException(status_code=409, detail=f"Paper is not ready ({document.status})")
    if document.pipeline_version != pipeline_version():
        raise HTTPException(status_code=409, detail="Paper belongs to another pipeline configuration; upload it again")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        chunks = retrieve_chunks(request.paper_id, request.question)
    except EmbeddingInputTooLongError:
        raise HTTPException(status_code=422, detail="Question exceeds the embedding model token limit") from None
    result = generate_answer(request.question, chunks)

    return ChatResponse(**result)
