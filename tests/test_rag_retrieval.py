"""Retrieval has to select, not just return whatever exists.

Before this work the knowledge base held 8 chunks while retrieve_context()
asked for 16, so every query got the entire corpus and the RAG stage could not
influence anything. Chunking made it worse: paragraphs accumulated up to 1200
characters regardless of headings, so Machine Learning, Data Analysis, and
Software Engineering bullets shared one chunk and no query could separate them.
"""

import pytest

from src.agents.jd_analyzer_agent import fallback_analyze_jd
from src.rag.build_vectorstore import (
    DISABLE_VECTORSTORE_ENV,
    FORCE_VECTORSTORE_ENV,
    get_or_build_vectorstore,
    has_semantic_embeddings,
)
from src.rag.knowledge_loader import load_all_knowledge_docs, split_markdown
from src.rag.retriever import retrieve_context, retrieve_snippets
from src.services.evaluation import rag_corpus_fraction
from src.services.llm_client import LocalHashEmbeddings
from src.ui.sample_data import SAMPLE_JDS, read_text

# retrieve_context asks for these per collection.
REQUESTED = {
    "resume_bullets": 5,
    "star_examples": 3,
    "skill_taxonomy": 3,
    "application_examples": 2,
    "interview_bank": 3,
}


@pytest.fixture(autouse=True)
def markdown_retrieval(monkeypatch):
    """Pin the deterministic retriever; Chroma presence is machine-local."""

    monkeypatch.setenv(DISABLE_VECTORSTORE_ENV, "1")


def _chunks_by_collection() -> dict[str, list]:
    grouped: dict[str, list] = {}
    for chunk in load_all_knowledge_docs():
        grouped.setdefault(chunk.metadata["collection"], []).append(chunk)
    return grouped


# --- chunking -------------------------------------------------------------


def test_each_chunk_covers_exactly_one_section():
    for chunk in load_all_knowledge_docs():
        headings = [line for line in chunk.content.splitlines() if line.startswith("#")]
        assert len(headings) <= 1, f"chunk spans several sections: {headings}"


def test_category_matches_the_heading_in_the_chunk():
    # The old accumulating splitter recorded only the last heading it absorbed,
    # so most chunks were mislabelled by their own metadata.
    for chunk in load_all_knowledge_docs():
        headings = [line for line in chunk.content.splitlines() if line.startswith("#")]
        if not headings:
            continue
        expected = headings[0].strip("# ").strip().lower().replace(" ", "_")
        assert chunk.metadata["category"] == expected


def test_sections_are_split_even_when_they_would_fit_one_chunk():
    content = "# Alpha\n\nalpha body\n\n# Beta\n\nbeta body\n"

    chunks = split_markdown(content, "f.md", "c", "t", chunk_size=10_000)

    assert [c.metadata["category"] for c in chunks] == ["alpha", "beta"]


def test_a_long_section_splits_but_keeps_its_heading():
    body = "\n\n".join(f"paragraph {i} with enough text to add up" * 3 for i in range(6))
    chunks = split_markdown(f"# Long Section\n\n{body}", "f.md", "c", "t", chunk_size=200)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content.startswith("# Long Section")
        assert chunk.metadata["category"] == "long_section"


def test_content_without_a_heading_still_produces_a_chunk():
    chunks = split_markdown("just a bare paragraph", "f.md", "c", "t")

    assert len(chunks) == 1
    assert chunks[0].metadata["category"] == "general"


# --- corpus size ----------------------------------------------------------


@pytest.mark.parametrize(("collection", "requested"), REQUESTED.items())
def test_every_collection_offers_more_than_the_retriever_asks_for(collection, requested):
    available = len(_chunks_by_collection().get(collection, []))

    assert available > requested, (
        f"{collection} holds {available} chunks against {requested} requested; "
        "retrieval cannot select from a corpus this small"
    )


# --- selectivity ----------------------------------------------------------


def _context_for(jd_path: str) -> dict:
    return retrieve_context(fallback_analyze_jd(read_text(jd_path)))


def test_different_roles_retrieve_different_context():
    contexts = {role: _context_for(path) for role, path in SAMPLE_JDS.items()}
    roles = list(contexts)

    for index, role in enumerate(roles):
        for other in roles[index + 1:]:
            assert contexts[role] != contexts[other], f"{role} and {other} got identical context"


def test_retrieval_reflects_the_role():
    ai = _context_for(SAMPLE_JDS["AI Intern"])
    swe = _context_for(SAMPLE_JDS["SWE Intern"])

    ai_bullets = " ".join(ai["bullet_templates"]).lower()
    swe_bullets = " ".join(swe["bullet_templates"]).lower()

    assert "machine learning" in ai_bullets
    assert "backend and api" in swe_bullets
    assert "backend and api" not in ai_bullets


def test_retrieval_does_not_return_the_whole_corpus():
    context = _context_for(SAMPLE_JDS["AI Intern"])

    assert rag_corpus_fraction(context) < 0.5


def test_snippets_are_capped_at_k():
    assert len(retrieve_snippets("python machine learning", "resume_bullets", k=2)) == 2


def test_heading_matches_outrank_incidental_body_mentions():
    top = retrieve_snippets("deep learning pytorch", "resume_bullets", k=1)[0]

    assert top.splitlines()[0] == "# Deep Learning"


# --- the metric -----------------------------------------------------------


def test_corpus_fraction_is_one_when_retrieval_had_no_choice():
    corpus_size = len(load_all_knowledge_docs())
    everything = {"c": ["snippet"] * corpus_size}

    assert rag_corpus_fraction(everything) == 1.0


def test_corpus_fraction_is_clamped_and_handles_empty_input():
    assert rag_corpus_fraction({}) == 0.0
    assert rag_corpus_fraction({"c": ["s"] * 10_000}) == 1.0


# --- vectorstore gating ---------------------------------------------------


def test_hash_embeddings_are_not_treated_as_semantic():
    assert has_semantic_embeddings() is False


@pytest.mark.parametrize(
    ("query", "unrelated"),
    [
        ("pytorch", "deep learning framework"),
        ("sql", "relational database queries"),
    ],
)
def test_hash_embeddings_capture_no_synonyms(query, unrelated):
    """The measurement behind skipping the vectorstore by default."""

    embeddings = LocalHashEmbeddings()
    a = embeddings.embed_query(query)
    b = embeddings.embed_query(unrelated)

    assert sum(x * y for x, y in zip(a, b, strict=True)) == 0.0


def test_vectorstore_is_skipped_when_embeddings_are_hash_based(monkeypatch):
    # Whether data/vectorstore/ exists is machine-local, so on a machine that
    # has run the app this gate is what keeps retrieval on the better path.
    monkeypatch.delenv(DISABLE_VECTORSTORE_ENV, raising=False)
    monkeypatch.delenv(FORCE_VECTORSTORE_ENV, raising=False)

    assert get_or_build_vectorstore() is None


def test_vectorstore_can_still_be_forced(monkeypatch):
    monkeypatch.delenv(DISABLE_VECTORSTORE_ENV, raising=False)
    monkeypatch.setenv(FORCE_VECTORSTORE_ENV, "1")

    # Either a store or None if chromadb is absent; the point is that the
    # embedding gate no longer short-circuits it.
    get_or_build_vectorstore()


def test_disable_beats_force(monkeypatch):
    monkeypatch.setenv(DISABLE_VECTORSTORE_ENV, "1")
    monkeypatch.setenv(FORCE_VECTORSTORE_ENV, "1")

    assert get_or_build_vectorstore() is None
