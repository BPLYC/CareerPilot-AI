"""Build or load the optional Chroma vectorstore."""

import os

from src.rag.knowledge_loader import load_all_knowledge_docs
from src.services.llm_client import get_embeddings


VECTORSTORE_PATH = os.path.join("data", "vectorstore")


def get_or_build_vectorstore():
    try:
        from langchain_community.vectorstores import Chroma
        from langchain_core.documents import Document
    except ImportError:
        return None

    embeddings = get_embeddings()
    if os.path.exists(VECTORSTORE_PATH) and os.listdir(VECTORSTORE_PATH):
        try:
            return Chroma(persist_directory=VECTORSTORE_PATH, embedding_function=embeddings)
        except ImportError:
            return None

    chunks = load_all_knowledge_docs()
    if not chunks:
        return None
    docs = [Document(page_content=chunk.content, metadata=chunk.metadata) for chunk in chunks]
    try:
        return Chroma.from_documents(docs, embeddings, persist_directory=VECTORSTORE_PATH)
    except ImportError:
        return None
