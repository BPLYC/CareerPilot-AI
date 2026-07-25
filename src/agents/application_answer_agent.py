"""Application answer drafting node."""

from src.agents.common import invoke_structured, run_node
from src.models.schemas import ApplicationAnswerSet, ApplicationQuestionAnswer
from src.services.prompts import APPLICATION_ANSWER_SYSTEM, context_block, schema_instruction
from src.services.structured_output import model_to_dict

SENSITIVE_NOTICE = (
    "签证、工作许可、担保、薪资和法律资格等问题必须由申请人本人填写。"
)
SENSITIVE_TERMS = (
    "visa",
    "work authorization",
    "authorization",
    "authorized",
    "sponsorship",
    "sponsor",
    "salary",
    "compensation",
    "eligible",
    "eligibility",
    "legal",
)


def _join(items: list[str], fallback: str) -> str:
    return ", ".join(items[:4]) if items else fallback


def is_sensitive_question(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in SENSITIVE_TERMS)


def _custom_answer(
    question: str,
    role: str,
    matched: str,
    project_name: str,
    project_description: str,
) -> dict:
    if is_sensitive_question(question):
        answer = SENSITIVE_NOTICE
        notice = SENSITIVE_NOTICE
    else:
        project_note = f" 具体示例可围绕“{project_name}”展开。"
        if project_description:
            project_note += f" 项目说明：{project_description}"
        answer = (
            f"回答思路：结合简历中已经验证的“{matched}”经历，说明其与“{role}”的关联。"
            f"{project_note}"
        )
        notice = f"以下仅为草稿，请在提交前调整语气和具体措辞。{SENSITIVE_NOTICE}"

    return model_to_dict(
        ApplicationQuestionAnswer(
            question=question,
            answer=answer,
            review_notice=notice,
        )
    )


def fallback_application_answers(
    resume_profile: dict,
    jd_analysis: dict,
    match_report: dict,
    application_questions: list[str] | None = None,
) -> dict:
    role = jd_analysis.get("job_title") or "该实习职位"
    matched = _join(match_report.get("matched_skills", []), "简历中已经体现的技能")
    projects = resume_profile.get("projects", [])
    project_name = projects[0].get("name", "简历中的相关项目") if projects else "简历中的相关项目"
    project_description = projects[0].get("description", "") if projects else ""
    missing = match_report.get("missing_skills", [])
    growth_note = f" 同时，我正在继续加强 {', '.join(missing[:2])}。" if missing else ""

    answers = ApplicationAnswerSet(
        why_this_role=(
            f"我对“{role}”感兴趣，因为它与我在“{matched}”方面的已有经历直接相关。"
            f"{growth_note}"
        ),
        key_strengths=(
            f"我与该职位最契合的部分，是简历中围绕“{matched}”体现的实践证据。"
            "我可以结合已经列出的课程、项目或实习经历进一步说明。"
        ),
        project_example=(
            f"我会重点介绍的一个例子是“{project_name}”。{project_description}".strip()
        ),
        custom_answers=[
            _custom_answer(question, role, matched, project_name, project_description)
            for question in (application_questions or [])
        ],
        review_notice=f"以下仅为草稿，请在提交前结合个人情况调整语气和示例。{SENSITIVE_NOTICE}",
    )
    return model_to_dict(answers)


def enforce_sensitive_question_boundaries(answers: dict, application_questions: list[str]) -> dict:
    if not application_questions:
        return answers

    custom_answers = {item.get("question", ""): dict(item) for item in answers.get("custom_answers", [])}
    sanitized = []
    for question in application_questions:
        item = custom_answers.get(question, {"question": question, "answer": "", "review_notice": ""})
        if is_sensitive_question(question):
            item["answer"] = SENSITIVE_NOTICE
            item["review_notice"] = SENSITIVE_NOTICE
        sanitized.append(
            model_to_dict(
                ApplicationQuestionAnswer(
                    question=question,
                    answer=item.get("answer") or "暂时无法生成回答思路，请依据真实情况手动填写。",
                    review_notice=item.get("review_notice") or "请在提交前检查并结合个人情况修改。",
                )
            )
        )

    updated = dict(answers)
    updated["custom_answers"] = sanitized
    return updated


def application_answer_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    match_report = state.get("match_report") or {}
    application_questions = state.get("application_questions") or []

    def from_llm() -> dict:
        user_prompt = (
            schema_instruction(
                "ApplicationAnswerSet",
                "why_this_role,key_strengths,project_example,custom_answers,review_notice",
            )
            + "\nUse only verified evidence. Do not answer sensitive eligibility questions.\n"
            + "For each requested application question, add one custom_answers item with question, answer, and review_notice.\n"
            + context_block(
                resume_profile=resume_profile,
                jd_analysis=jd_analysis,
                match_report=match_report,
                application_questions=application_questions,
                rag_context=state.get("retrieved_context", {}),
            )
        )
        return invoke_structured(ApplicationAnswerSet, APPLICATION_ANSWER_SYSTEM, user_prompt)

    return run_node(
        node_name="ApplicationAnswerNode",
        output_key="application_answers",
        llm_branch=from_llm,
        fallback_branch=lambda: fallback_application_answers(
            resume_profile, jd_analysis, match_report, application_questions
        ),
        describe=lambda _: "已生成基于简历证据的保守申请回答思路。",
        # Runs on the fallback path too. These are the visa, sponsorship, and
        # compensation boundaries, which must hold however the answers arrived.
        refine=lambda answers: enforce_sensitive_question_boundaries(answers, application_questions),
    )
