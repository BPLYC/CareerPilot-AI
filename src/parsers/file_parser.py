"""Unified uploaded resume parser."""

from src.parsers.docx_parser import parse_docx
from src.parsers.pdf_parser import parse_pdf


def _read_text_file(uploaded_file) -> str:
    content = uploaded_file.read()
    if isinstance(content, str):
        return content
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def parse_resume_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    filename = uploaded_file.name.lower()
    if filename.endswith(".txt"):
        return _read_text_file(uploaded_file)
    if filename.endswith(".pdf"):
        return parse_pdf(uploaded_file)
    if filename.endswith(".docx"):
        return parse_docx(uploaded_file)
    raise ValueError(f"Unsupported file type: {filename}")
