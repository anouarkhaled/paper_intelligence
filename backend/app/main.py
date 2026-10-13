from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api import chat, papers
from app.services.document_store import DocumentStore
from app.settings import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    store = DocumentStore.from_settings()
    await run_in_threadpool(store.initialize)
    app.state.document_store = store
    yield


app = FastAPI(title="Research Paper Assistant", lifespan=lifespan)

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
