"""PDF resume parsing with PyMuPDF."""


def parse_pdf(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install pymupdf to parse PDF files.") from exc

    file_bytes = uploaded_file.read()
    if not file_bytes:
        return ""

    text_parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(part for part in text_parts if part).strip()
