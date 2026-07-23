"""Load and chunk local knowledge-base markdown files."""

import os
from dataclasses import dataclass

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


def load_all_knowledge_docs(base_dir: str = KNOWLEDGE_BASE_DIR) -> list[KnowledgeChunk]:
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
    return heading.strip("# ").strip().lower().replace(" ", "_") or "general"


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

        current = section_heading + "\n\n" if section_heading else ""
        emitted = False
        for paragraph in paragraphs:
            if current.strip() and len(current) + len(paragraph) > chunk_size:
                chunks.append(KnowledgeChunk(current.strip(), dict(metadata)))
                emitted = True
                # Repeat the heading so a continuation chunk still says what it is.
                current = section_heading + "\n\n" if section_heading else ""
            current += paragraph + "\n\n"
        if current.strip() and (paragraphs or not emitted):
            chunks.append(KnowledgeChunk(current.strip(), dict(metadata)))
    return chunks
