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
    context = "\n\n".join(
        f"[Section: {chunk['section']}, Page: {chunk['page']}]\n{chunk['text']}"
        for chunk in chunks
    )
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)

    response = _get_llm().invoke(prompt)

    seen = set()
    citations = []
    for chunk in chunks:
        key = (chunk["section"], chunk["page"])
        if key not in seen:
            seen.add(key)
            citations.append({"section": chunk["section"], "page": chunk["page"]})

    return {"answer": response.content, "citations": citations}
