from functools import lru_cache

from langchain_groq import ChatGroq

from app.settings import get_settings


@lru_cache
def _get_llm() -> ChatGroq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is required to generate answers")
    return ChatGroq(model=settings.llm_model, api_key=settings.groq_api_key, temperature=0)


PROMPT_TEMPLATE = """Answer the question using only the context below. \
If the context doesn't contain the answer, say so — do not make one up.

Context:
{context}

Question: {question}
Answer:"""


def generate_answer(question: str, chunks: list[dict]) -> dict:
    def citation(chunk):
        pages = chunk.get("pages", [chunk["page"]] if chunk.get("page") is not None else [])
        return {
            "section": chunk["section"], "page": pages[0] if pages else None,
            "pages": pages, "page_start": pages[0] if pages else None,
            "page_end": pages[-1] if pages else None,
            "provenance_complete": chunk.get("provenance_complete", False),
        }

    context = "\n\n".join(
        f"[Section: {chunk['section']}, Pages: {citation(chunk)['pages'] or 'unknown'}]\n{chunk['text']}"
        for chunk in chunks
    )
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)

    response = _get_llm().invoke(prompt)

    seen = set()
    citations = []
    for chunk in chunks:
        source = citation(chunk)
        key = (source["section"], tuple(source["pages"]), source["provenance_complete"])
        if key not in seen:
            seen.add(key)
            citations.append(source)

    return {"answer": response.content, "citations": citations}
