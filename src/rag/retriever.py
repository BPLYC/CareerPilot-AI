"""Knowledge retrieval interface."""

from src.rag.build_vectorstore import get_or_build_vectorstore
from src.rag.knowledge_loader import load_all_knowledge_docs


def _score(query: str, content: str) -> int:
    query_terms = {term.lower().strip(",.") for term in query.split() if len(term) > 2}
    content_lower = content.lower()
    return sum(1 for term in query_terms if term in content_lower)


def fallback_retrieve(query: str, collection: str, k: int) -> list[str]:
    chunks = [chunk for chunk in load_all_knowledge_docs() if chunk.metadata.get("collection") == collection]
    ranked = sorted(chunks, key=lambda chunk: _score(query, chunk.content), reverse=True)
    return [chunk.content for chunk in ranked[:k]]


def retrieve_snippets(query: str, collection: str, k: int = 3) -> list[str]:
    vectorstore = get_or_build_vectorstore()
    if vectorstore is None:
        return fallback_retrieve(query, collection, k)
    try:
        docs = vectorstore.similarity_search(query, k=k, filter={"collection": collection})
        return [doc.page_content for doc in docs]
    except Exception:
        return fallback_retrieve(query, collection, k)


def retrieve_context(jd_analysis: dict) -> dict:
    required = jd_analysis.get("required_skills", [])[:5]
    tools = jd_analysis.get("tools_and_technologies", [])[:3]
    query = f"{jd_analysis.get('job_title', 'internship')} internship {' '.join(required)} {' '.join(tools)}"
    return {
        "bullet_templates": retrieve_snippets(query, "resume_bullets", 5),
        "star_examples": retrieve_snippets(query, "star_examples", 3),
        "skill_taxonomy": retrieve_snippets(query, "skill_taxonomy", 3),
        "application_examples": retrieve_snippets(query, "application_examples", 2),
        "interview_bank": retrieve_snippets(query, "interview_bank", 3),
    }
