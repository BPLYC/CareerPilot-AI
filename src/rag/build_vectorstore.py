"""Build or load the optional Chroma vectorstore."""

import os

from src.rag.knowledge_loader import load_all_knowledge_docs
from src.services.llm_client import LocalHashEmbeddings, get_embeddings

VECTORSTORE_PATH = os.path.join("data", "vectorstore")

# Set to force the deterministic markdown retriever. Whether data/vectorstore/
# exists is machine-local state that git does not track, so retrieval results
# otherwise differ between a fresh checkout and a machine that has run the app.
# Evaluation runs set this so their numbers are comparable across machines.
DISABLE_VECTORSTORE_ENV = "CAREERPILOT_DISABLE_VECTORSTORE"

# Use the vectorstore even with hash embeddings. Off by default because that
# combination retrieves worse than term matching; see has_semantic_embeddings().
FORCE_VECTORSTORE_ENV = "CAREERPILOT_FORCE_VECTORSTORE"


def has_semantic_embeddings() -> bool:
    """Whether the configured embeddings carry meaning, rather than hashing tokens.

    LocalHashEmbeddings buckets each token by md5 into 64 dimensions. Two
    consequences make it a poor basis for similarity search:

    - No synonym capture at all. Measured on this knowledge base, the cosine
      similarity of "pytorch" against "deep learning framework" is 0.000, as it
      is for "sql" against "relational database queries".
    - Heavy collisions. 839 distinct tokens over 64 buckets averages 13 tokens
      per dimension, so unrelated words such as "docker" and "causation" become
      the same feature.

    Ranking by term overlap beats it: with hash embeddings the vectorstore put
    "Data Analysis" above "Software Engineering" for a backend role and returned
    identical skill snippets for the analyst and engineer roles.
    """

    try:
        return not isinstance(get_embeddings(), LocalHashEmbeddings)
    except Exception:
        # EMBEDDING_PROVIDER=openai with no OpenAI key raises here. Retrieval is
        # an optional enhancement, so fall back to the markdown path rather than
        # aborting the whole analysis on a provider misconfiguration.
        return False


def get_or_build_vectorstore():
    if os.environ.get(DISABLE_VECTORSTORE_ENV):
        return None
    if not has_semantic_embeddings() and not os.environ.get(FORCE_VECTORSTORE_ENV):
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
