from pydantic import BaseModel, Field


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
    page: int | None = None
    pages: list[int] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    provenance_complete: bool = False


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
