from pydantic import BaseModel


class UploadResponse(BaseModel):
    paper_id: str
    filename: str
    num_pages: int
    num_chunks: int


class ChatRequest(BaseModel):
    paper_id: str
    question: str


class Citation(BaseModel):
    section: str
    page: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
