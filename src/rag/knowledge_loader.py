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


def split_markdown(content: str, source: str, collection: str, doc_type: str, chunk_size: int = 1200) -> list[KnowledgeChunk]:
    paragraphs = [part.strip() for part in content.split("\n\n") if part.strip()]
    chunks = []
    current = ""
    category = "general"
    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            category = paragraph.strip("# ").lower().replace(" ", "_")
        if len(current) + len(paragraph) > chunk_size and current:
            chunks.append(KnowledgeChunk(current.strip(), {"source": source, "collection": collection, "type": doc_type, "category": category}))
            current = ""
        current += paragraph + "\n\n"
    if current.strip():
        chunks.append(KnowledgeChunk(current.strip(), {"source": source, "collection": collection, "type": doc_type, "category": category}))
    return chunks
