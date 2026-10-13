from fastapi import Request

from app.services.document_store import DocumentStore

# Single-user development mode, not authentication. Never accept this from clients.
LOCAL_OWNER_ID = "local"


def get_document_store(request: Request) -> DocumentStore:
    return request.app.state.document_store
