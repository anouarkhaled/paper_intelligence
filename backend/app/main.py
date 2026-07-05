from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, papers

load_dotenv()

app = FastAPI(title="Research Paper Assistant")

# MVP: frontend runs on Vite's default dev port. Tighten this to a real
# origin allowlist before any non-local deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}
