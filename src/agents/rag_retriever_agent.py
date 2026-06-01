"""RAG retrieval node."""

from src.rag.retriever import retrieve_context


def rag_retriever_node(state) -> dict:
    context = retrieve_context(state.get("jd_analysis") or {})
    count = sum(len(value) for value in context.values())
    return {
        "retrieved_context": context,
        "workflow_trace": [f"RAGRetrieverNode: Retrieved {count} knowledge snippets from local knowledge base."],
    }
