from fastapi import APIRouter, HTTPException

from app.api.papers import papers
from app.models.schemas import ChatRequest, ChatResponse
from app.rag.generation import generate_answer
from app.rag.retriever import retrieve_chunks

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if request.paper_id not in papers:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    chunks = retrieve_chunks(request.paper_id, request.question)
    result = generate_answer(request.question, chunks)

    return ChatResponse(**result)
