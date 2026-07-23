"""Knowledge retrieval interface."""

from src.rag.build_vectorstore import get_or_build_vectorstore
from src.rag.knowledge_loader import load_all_knowledge_docs

HEADING_WEIGHT = 3

# Words that join a heading rather than describe it. "Backend And API" and
# "Testing And Quality" would otherwise both score on "and" alone, and outrank
# a genuinely relevant heading on a term that means nothing.
HEADING_STOPWORDS = {"and", "the", "for", "with", "from", "into"}


def _query_terms(query: str) -> set[str]:
    return {term.lower().strip(",.") for term in query.split() if len(term) > 2}


def _score(query: str, content: str, category: str = "") -> int:
    """Rank a chunk against the query, weighting its section heading.

    Each chunk is one markdown section, so its heading says what the section is
    about far more reliably than any single line of the body. A "Backend And
    API" section and a "Deep Learning" section both mention Python; only the
    heading separates them.

    A heading term is also present in the body, so a heading hit scores
    1 + HEADING_WEIGHT in total.
    """

    terms = _query_terms(query)
    content_lower = content.lower()
    body_score = sum(1 for term in terms if term in content_lower)

    # Whole-word match against the heading, not a substring test: "api" should
    # not score against "rapid", and a multi-word query term should not match a
    # heading merely because it shares a fragment.
    category_words = set((category or "").replace("_", " ").split()) - HEADING_STOPWORDS
    heading_score = sum(1 for term in terms if term in category_words)
    return body_score + HEADING_WEIGHT * heading_score


def fallback_retrieve(query: str, collection: str, k: int) -> list[str]:
    chunks = [chunk for chunk in load_all_knowledge_docs() if chunk.metadata.get("collection") == collection]
    ranked = sorted(
        chunks,
        key=lambda chunk: _score(query, chunk.content, chunk.metadata.get("category", "")),
        reverse=True,
    )
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
