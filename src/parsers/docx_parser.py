"""DOCX resume parsing."""


def parse_docx(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install python-docx to parse DOCX files.") from exc

    document = Document(uploaded_file)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs).strip()
