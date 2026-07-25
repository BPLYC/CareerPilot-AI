"""Structured models used by CareerPilot AI."""

from pydantic import AliasChoices, BaseModel, Field


class Education(BaseModel):
    school: str = Field(default="unknown")
    degree: str = Field(default="unknown")
    major: str = Field(default="unknown")
    graduation_date: str = Field(default="unknown")


class ProjectExperience(BaseModel):
    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    outcome: str = Field(default="")


class WorkExperience(BaseModel):
    company: str
    role: str = Field(validation_alias=AliasChoices("role", "title", "position"))
    duration: str = Field(default="")
    description: str


class ResumeProfile(BaseModel):
    name: str = Field(default="unknown")
    email: str = Field(default="unknown")
    phone: str = Field(default="unknown")
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectExperience] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)


class JobDescriptionAnalysis(BaseModel):
    job_title: str = Field(default="unknown")
    company: str = Field(default="unknown")
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    education_requirements: str = Field(default="")
    experience_requirements: str = Field(default="")
    tools_and_technologies: list[str] = Field(default_factory=list)


class MatchReport(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    relevant_projects: list[str] = Field(default_factory=list)
    weak_sections: list[str] = Field(default_factory=list)
    explanation: str = Field(default="")
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    score_reliable: bool = Field(default=True)
    scoring_warnings: list[str] = Field(default_factory=list)


class BulletSuggestion(BaseModel):
    context: str
    original_bullet: str = Field(default="", validation_alias=AliasChoices("original_bullet", "original"))
    optimized_bullet: str = Field(
        validation_alias=AliasChoices(
            "optimized_bullet",
            "bullet",
            "optimized",
            "optimized_text",
            "suggestion",
            "suggested_bullet",
            "suggested_text",
            "improved_bullet",
            "rewritten_bullet",
            "new_bullet",
        )
    )
    rationale: str = Field(validation_alias=AliasChoices("rationale", "reason", "explanation"))
    is_revised_by_reflection: bool = Field(default=False)


class ApplicationQuestionAnswer(BaseModel):
    question: str
    answer: str
    review_notice: str = Field(default="Review and personalize before submitting.")


class ApplicationAnswerSet(BaseModel):
    why_this_role: str = Field(default="")
    key_strengths: str = Field(default="")
    project_example: str = Field(default="")
    custom_answers: list[ApplicationQuestionAnswer] = Field(default_factory=list)
    review_notice: str = Field(default="Review and personalize before submitting.")


class InterviewQuestion(BaseModel):
    question: str
    focus_area: str = Field(default="")
    prep_notes: str = Field(default="")
