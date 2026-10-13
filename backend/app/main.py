from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, papers
from app.settings import get_settings

settings = get_settings()

app = FastAPI(title="Research Paper Assistant")

# MVP: frontend runs on Vite's default dev port. Tighten this to a real
# origin allowlist before any non-local deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}
