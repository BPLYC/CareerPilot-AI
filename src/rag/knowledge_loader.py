"""Load and chunk local knowledge-base markdown files."""

import os
from dataclasses import dataclass
from functools import lru_cache

KNOWLEDGE_BASE_DIR = os.path.join("data", "knowledge_base")


@dataclass
class KnowledgeChunk:
    content: str
    metadata: dict


SOURCE_COLLECTIONS = {
    "resume_bullet_templates.md": ("resume_bullets", "bullet_template"),
    "star_method_examples.md": ("star_examples", "star_example"),
    "ai_ds_swe_internship_skill_taxonomy.md": ("skill_taxonomy", "skill"),
    "application_question_examples.md": ("application_examples", "application"),
    "interview_question_bank.md": ("interview_bank", "interview"),
}


@lru_cache(maxsize=4)
def load_all_knowledge_docs(base_dir: str = KNOWLEDGE_BASE_DIR) -> list[KnowledgeChunk]:
    """Read and chunk the knowledge base.

    Cached because retrieve_context() asks for five collections and each call
    re-read and re-parsed every file. The knowledge base is static at runtime;
    tests that edit it should call load_all_knowledge_docs.cache_clear().
    """

    chunks = []
    if not os.path.isdir(base_dir):
        return chunks
    for filename, (collection, doc_type) in SOURCE_COLLECTIONS.items():
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        chunks.extend(split_markdown(content, filename, collection, doc_type))
    return chunks


def _category_of(heading: str) -> str:
    # Collapse whitespace first: a heading written without a blank line after it
    # arrives here with its body attached, and would otherwise become a category
    # containing newlines.
    collapsed = " ".join(heading.strip("# ").split())
    return collapsed.lower().replace(" ", "_") or "general"


def split_markdown(content: str, source: str, collection: str, doc_type: str, chunk_size: int = 1200) -> list[KnowledgeChunk]:
    """Split a knowledge file into one chunk per markdown section.

    Sections are the unit of meaning here: "Machine Learning" bullets and
    "Software Engineering" bullets answer different queries, so they have to be
    separately retrievable.

    This used to accumulate paragraphs up to chunk_size regardless of headings,
    which packed Machine Learning, Data Analysis, and Software Engineering into
    a single chunk. Retrieval then returned the same text for an AI role and a
    backend role, and `category` recorded only the last heading absorbed, so it
    mislabelled most of what it described.

    Sections longer than chunk_size are still split, on paragraph boundaries,
    with the heading repeated so every part stays self-describing.

    Any `#` level starts a new section, so a `## Child` chunk does not record
    its `# Parent`. The knowledge files are flat today; if they gain subsections
    that only make sense under their parent, carry the ancestor into the chunk.
    """

    sections: list[tuple[str, list[str]]] = []
    heading = ""
    body: list[str] = []
    for paragraph in [part.strip() for part in content.split("\n\n") if part.strip()]:
        if paragraph.startswith("#"):
            if heading or body:
                sections.append((heading, body))
            heading, body = paragraph, []
        else:
            body.append(paragraph)
    if heading or body:
        sections.append((heading, body))

    chunks = []
    for section_heading, paragraphs in sections:
        category = _category_of(section_heading) if section_heading else "general"
        metadata = {"source": source, "collection": collection, "type": doc_type, "category": category}

        prefix = section_heading + "\n\n" if section_heading else ""
        current = prefix
        # Track the body separately: `current` is seeded with the heading and so
        # is always truthy, and flushing on that alone emits a chunk holding
        # nothing but the heading whenever the first paragraph already exceeds
        # chunk_size. Such a chunk still scores on its heading, so it would win
        # a retrieval slot and hand the prompt an empty snippet.
        has_body = False
        for paragraph in paragraphs:
            if has_body and len(current) + len(paragraph) > chunk_size:
                chunks.append(KnowledgeChunk(current.strip(), dict(metadata)))
                current = prefix
                has_body = False
            current += paragraph + "\n\n"
            has_body = True
        if current.strip():
            chunks.append(KnowledgeChunk(current.strip(), dict(metadata)))
    return chunks
