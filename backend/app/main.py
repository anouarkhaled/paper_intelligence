from fastapi import FastAPI

app = FastAPI(title="Research Paper Assistant")


@app.get("/health")
def health():
    return {"status": "ok"}
