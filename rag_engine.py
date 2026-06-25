"""
RAG Engine — retrieves relevant book passages for a user query.

Called by chat_engine.py on every user message.
"""

from pathlib import Path
from functools import lru_cache

CHROMA_DIR = Path(__file__).parent / "chroma_db"
_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = client.get_collection(
            name="vedic_books",
            embedding_function=emb_fn,
        )
        return _collection
    except Exception as e:
        print(f"[RAG] ChromaDB not available: {e}")
        return None


def retrieve(query: str, n_results: int = 4) -> list[dict]:
    """
    Returns a list of dicts: {text, source}
    Returns empty list if index not built yet.
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        passages = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            passages.append({
                "text": doc,
                "source": meta.get("source", "Unknown"),
            })
        return passages
    except Exception as e:
        print(f"[RAG] Query error: {e}")
        return []


def format_context(passages: list[dict]) -> str:
    """Format retrieved passages for injection into system prompt."""
    if not passages:
        return ""
    lines = ["RELEVANT KNOWLEDGE CONTEXT (use this to inform your answer — do not cite or reference any source):"]
    for i, p in enumerate(passages, 1):
        lines.append(f"\n[Context {i}]")
        lines.append(p["text"][:600])  # cap length
    return "\n".join(lines)
