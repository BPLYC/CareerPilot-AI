"""Interview preparation node."""

from src.agents.common import invoke_structured_list, run_node
from src.models.schemas import InterviewQuestion
from src.services.prompts import INTERVIEW_COACH_SYSTEM, context_block
from src.services.structured_output import model_to_dict, validate_dict


def _project_questions(projects: list[dict]) -> list[dict]:
    questions = []
    for project in projects[:2]:
        name = project.get("name", "你的项目")
        technologies = ", ".join(project.get("technologies", [])[:4])
        tech_note = f" 请准备说明 {technologies} 的具体用途。" if technologies else ""
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question=f"请介绍一下“{name}”：它解决了什么问题，你做过哪些取舍？",
                    focus_area="项目深挖",
                    prep_notes=f"只使用简历中已经出现的实现细节和结果。{tech_note}",
                )
            )
        )
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question=f"如果继续完善“{name}”，你下一步会改进或衡量什么？",
                    focus_area="项目追问",
                    prep_notes="回答应基于当前项目范围，不要把尚未实现的功能描述成既有成果。",
                )
            )
        )
    return questions


def _role_specific_questions(jd_analysis: dict) -> list[dict]:
    title = (jd_analysis.get("job_title") or "").lower()
    evidence = " ".join(
        jd_analysis.get("required_skills", [])
        + jd_analysis.get("tools_and_technologies", [])
        + jd_analysis.get("keywords", [])
    ).lower()
    questions = []

    if any(term in title + " " + evidence for term in ["machine learning", "ml", "ai", "pytorch", "tensorflow"]):
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="你会如何判断一次模型改进是真实有效，而不是随机波动？",
                    focus_area="机器学习评估",
                    prep_notes="结合验证数据、指标、误差分析和自己真实完成的项目回答。",
                )
            )
        )

    if any(term in title + " " + evidence for term in ["data analyst", "analytics", "sql", "dashboard", "tableau"]):
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="How would you check whether a dashboard metric is trustworthy?",
                    focus_area="Analytics validation",
                    prep_notes="Discuss source data, joins, filters, edge cases, and sanity checks you have used before.",
                )
            )
        )

    if any(term in title + " " + evidence for term in ["software", "backend", "api", "flask", "docker", "rest"]):
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="How would you debug a failing API endpoint in a deployed internship project?",
                    focus_area="Software engineering",
                    prep_notes="Walk through logs, reproduction steps, request data, dependencies, and a small verified fix.",
                )
            )
        )

    return questions


def fallback_interview_questions(resume_profile: dict, jd_analysis: dict, retrieved_context: dict) -> list[dict]:
    questions = _project_questions(resume_profile.get("projects", []))
    questions.extend(_role_specific_questions(jd_analysis))
    for skill in jd_analysis.get("required_skills", [])[:3]:
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question=f"你在项目或课程作业中如何使用过 {skill}？",
                    focus_area="必需技能证据",
                    prep_notes="基于简历中的真实例子准备一段 STAR 结构回答。",
                )
            )
        )

    bank = " ".join(retrieved_context.get("interview_bank", []))
    if "unclear requirements" in bank.lower():
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="面对不明确的需求时，你通常如何处理？",
                    focus_area="行为面试",
                    prep_notes="说明你在过去项目中实际采用过的澄清步骤。",
                )
            )
        )

    if not questions:
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="请介绍一个简历中的技术项目。",
                    focus_area="综合问题",
                    prep_notes="选择一个真实项目，按情境、任务、行动和结果进行准备。",
                )
            )
        )
    return questions[:6]


def interview_coach_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    retrieved_context = state.get("retrieved_context") or {}

    def from_llm() -> list[dict]:
        user_prompt = (
            "Return a JSON array of InterviewQuestion objects with question, focus_area, and prep_notes. "
            "Questions must include role-specific technical practice and project deep-dive follow-ups "
            "grounded in the resume/JD evidence.\n"
            + context_block(
                resume_profile=resume_profile,
                jd_analysis=jd_analysis,
                rag_context=retrieved_context,
            )
        )
        raw = invoke_structured_list(INTERVIEW_COACH_SYSTEM, user_prompt, "interview questions")
        return [model_to_dict(validate_dict(InterviewQuestion, item)) for item in raw]

    return run_node(
        node_name="InterviewCoachNode",
        output_key="interview_questions",
        llm_branch=from_llm,
        fallback_branch=lambda: fallback_interview_questions(resume_profile, jd_analysis, retrieved_context),
        describe=lambda questions: f"已生成 {len(questions)} 道面试练习题。",
    )
