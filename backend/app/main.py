from dotenv import load_dotenv
from fastapi import FastAPI

from app.api import chat, papers

load_dotenv()

app = FastAPI(title="Research Paper Assistant")
app.include_router(papers.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}
