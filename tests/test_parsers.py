"""Upload parsing had no test coverage at all.

Resumes arrive as user-supplied files, so these paths see whatever a student's
laptop produces: BOM-prefixed exports, legacy encodings, empty files, and the
occasional wrong extension.
"""

import io

import pytest

from src.parsers.docx_parser import parse_docx
from src.parsers.file_parser import parse_resume_file
from src.parsers.pdf_parser import parse_pdf

RESUME_TEXT = "Alex Chen\nSkills: Python, SQL\nProject: Task Manager"


class Upload(io.BytesIO):
    """Stands in for a Streamlit UploadedFile, which is a named binary stream."""

    def __init__(self, name: str, data: bytes):
        super().__init__(data)
        self.name = name


def _pdf_bytes(text: str = RESUME_TEXT) -> bytes:
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _docx_bytes(paragraphs: list[str]) -> bytes:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_none_upload_returns_empty_string():
    assert parse_resume_file(None) == ""
    assert parse_pdf(None) == ""
    assert parse_docx(None) == ""


@pytest.mark.parametrize(
    ("encoding", "raw"),
    [
        ("utf-8", RESUME_TEXT.encode("utf-8")),
        ("utf-8-sig", RESUME_TEXT.encode("utf-8-sig")),
        ("latin-1", "Alex Chen\nCafé project".encode("latin-1")),
    ],
)
def test_txt_decodes_common_encodings(encoding, raw):
    text = parse_resume_file(Upload("resume.txt", raw))

    assert "Alex Chen" in text


def test_txt_with_undecodable_bytes_does_not_raise():
    # Better to hand the workflow a slightly mangled resume than to crash on
    # upload; the user can still see and correct what was read.
    text = parse_resume_file(Upload("resume.txt", b"Alex \xff\xfe Chen"))

    assert "Alex" in text


def test_empty_txt_returns_empty_string():
    assert parse_resume_file(Upload("resume.txt", b"")) == ""


def test_pdf_round_trip():
    text = parse_resume_file(Upload("resume.pdf", _pdf_bytes()))

    assert "Alex Chen" in text


def test_empty_pdf_upload_returns_empty_string():
    assert parse_resume_file(Upload("resume.pdf", b"")) == ""


def test_docx_round_trip():
    data = _docx_bytes(["Alex Chen", "", "   ", "Skills: Python, SQL"])
    text = parse_resume_file(Upload("resume.docx", data))

    assert "Alex Chen" in text
    assert "Skills: Python, SQL" in text
    # Blank and whitespace-only paragraphs are dropped rather than becoming
    # empty lines in the resume text.
    assert "\n\n" not in text


def test_extension_matching_is_case_insensitive():
    text = parse_resume_file(Upload("RESUME.TXT", RESUME_TEXT.encode("utf-8")))

    assert "Alex Chen" in text


def test_unsupported_extension_is_rejected_by_name():
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_resume_file(Upload("resume.rtf", b"whatever"))


@pytest.mark.parametrize("name", ["resume.pdf", "resume.docx"])
def test_corrupt_binary_upload_raises_rather_than_returning_junk(name):
    # app.py wraps the call in try/except and surfaces the message, so raising
    # is acceptable. Silently returning garbage text would not be: it would be
    # analysed as though it were the applicant's resume.
    with pytest.raises(Exception):  # noqa: B017 - the library's type is not part of our contract
        parse_resume_file(Upload(name, b"not really a document"))
