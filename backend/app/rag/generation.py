from functools import lru_cache

from langchain_groq import ChatGroq

# Groq's model catalog changes over time — if this model is retired,
# check current options at console.groq.com/docs/models and swap it here.
MODEL_NAME = "llama-3.3-70b-versatile"


@lru_cache
def _get_llm() -> ChatGroq:
    # Lazy + cached: created on first real use, not at import time. This
    # matters because it reads GROQ_API_KEY from the environment, and we
    # don't want to depend on import order (main.py loading .env before
    # this module gets imported) just to have a valid key available.
    return ChatGroq(model=MODEL_NAME, temperature=0)


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
