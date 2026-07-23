"""Build or load the optional Chroma vectorstore."""

import os

from src.rag.knowledge_loader import load_all_knowledge_docs
from src.services.llm_client import get_embeddings

VECTORSTORE_PATH = os.path.join("data", "vectorstore")

# Set to force the deterministic markdown retriever. Whether data/vectorstore/
# exists is machine-local state that git does not track, so retrieval results
# otherwise differ between a fresh checkout and a machine that has run the app.
# Evaluation runs set this so their numbers are comparable across machines.
DISABLE_VECTORSTORE_ENV = "CAREERPILOT_DISABLE_VECTORSTORE"


def get_or_build_vectorstore():
    if os.environ.get(DISABLE_VECTORSTORE_ENV):
        return None
    try:
        from langchain_chroma import Chroma
        from langchain_core.documents import Document
    except ImportError:
        return None

    embeddings = get_embeddings()
    if os.path.exists(VECTORSTORE_PATH) and os.listdir(VECTORSTORE_PATH):
        try:
            return Chroma(persist_directory=VECTORSTORE_PATH, embedding_function=embeddings)
        except Exception:
            return None

    chunks = load_all_knowledge_docs()
    if not chunks:
        return None
    docs = [Document(page_content=chunk.content, metadata=chunk.metadata) for chunk in chunks]
    try:
        return Chroma.from_documents(docs, embeddings, persist_directory=VECTORSTORE_PATH)
    except Exception:
        return None
