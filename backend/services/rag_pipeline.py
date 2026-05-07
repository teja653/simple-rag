from backend.services.embedding_service import get_embedding
from backend.services.vector_store import search_similar
from backend.services.llm_service import get_response


def generate_answer(query):
    query_embedding = get_embedding(query)

    docs = search_similar(query_embedding)

    context = "\n".join(docs)

    prompt = f"""
You are a helpful AI assistant.
Answer ONLY from the context below.

Context:
{context}

Question:
{query}

Answer:
"""

    return get_response(prompt)