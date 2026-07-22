"""The context we hand the model must be in the format we ask it to reply in."""

import json

import pytest

from src.services.prompts import context_block
from src.services.skill_taxonomy import KNOWN_SKILLS, find_known_skills


def _section_body(rendered: str, label: str) -> str:
    lines = rendered.splitlines()
    return lines[lines.index(f"{label}:") + 1]


def test_sections_are_valid_json():
    rendered = context_block(
        resume_profile={"name": "Alex Chen", "skills": ["Python"], "gpa": None, "verified": True},
        jd_analysis={"required_skills": ["SQL"]},
    )

    profile = json.loads(_section_body(rendered, "Resume profile"))
    assert profile["gpa"] is None
    assert profile["verified"] is True
    assert json.loads(_section_body(rendered, "Jd analysis"))["required_skills"] == ["SQL"]


def test_apostrophes_do_not_switch_the_quoting_style():
    # str() on this dict yields {'note': "Dean's List"} -- two quoting styles in
    # one object, and neither key nor value parseable as JSON.
    rendered = context_block(resume_profile={"note": "Dean's List"})

    assert json.loads(_section_body(rendered, "Resume profile")) == {"note": "Dean's List"}


def test_plain_strings_pass_through_unquoted():
    rendered = context_block(reflection_feedback="Remove unsupported numbers.")

    assert _section_body(rendered, "Reflection feedback") == "Remove unsupported numbers."


def test_unserialisable_values_do_not_raise():
    rendered = context_block(resume_profile={"parsed_at": object()})

    assert isinstance(json.loads(_section_body(rendered, "Resume profile"))["parsed_at"], str)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Built a Flask API with Python and SQL", ["Python", "SQL", "Flask"]),
        ("no relevant technology here", []),
        ("", []),
    ],
)
def test_find_known_skills_returns_taxonomy_order(text, expected):
    assert find_known_skills(text) == expected


def test_taxonomy_has_no_duplicates():
    assert len(KNOWN_SKILLS) == len(set(KNOWN_SKILLS))
