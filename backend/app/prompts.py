from .models import QuestionType


BASE_SYSTEM = """You are a silent interview copilot displayed on a phone.
Generate concise, interview-ready notes the candidate can speak naturally.
Do not mention that you are an AI. Avoid long essays. Prefer direct bullets.
If the question is ambiguous, give a practical answer with assumptions."""


def _profile_block(profile) -> str:
    if not profile:
        return ""
    parts = [f"Strongest language: {profile.primary_language}."]
    if profile.secondary_languages:
        parts.append(f"Also knows: {', '.join(profile.secondary_languages)}.")
    if profile.frameworks:
        parts.append(f"Familiar frameworks/tools: {', '.join(profile.frameworks)}.")
    if profile.domains:
        parts.append(f"Domains: {', '.join(profile.domains)}.")
    if profile.seniority:
        parts.append(f"Seniority: {profile.seniority}.")
    return (
        "Candidate skill profile (derived from their resume):\n"
        + " ".join(parts)
        + f"\nWrite code idiomatic to a {profile.seniority} {profile.primary_language} "
        "engineer, using their frameworks when relevant."
    )


def build_prompt(
    question: str,
    question_type: QuestionType,
    mode: str = "normal",
    context: str | None = None,
    language: str = "Python",
    profile=None,
) -> str:
    length_instruction = {
        "short": "Keep the answer very short: 3-5 bullets max.",
        "regenerate": "Provide an alternative answer with a different wording.",
    }.get(mode, "Keep the answer compact but complete.")

    formats = {
        QuestionType.coding: f"""Return:
Approach:
Code: use {language} unless the question explicitly asks otherwise
Complexity:
Edge cases:""",
        QuestionType.aws: """Return:
Direct answer:
Real-world example:
Interview tip:""",
        QuestionType.system_design: """Return:
Clarifying assumptions:
Core components:
Data model / database:
Scaling and reliability:
Tradeoffs:""",
        QuestionType.hr: """Return a polished first-person answer that sounds natural and professional.""",
        QuestionType.project: """Return only reminder points. Focus on AIOps/OpsMitra style platform details, architecture, impact, and ownership. Keep it brief because the candidate already knows the project.""",
        QuestionType.concept: """Return:
Definition:
Simple example:
Interview-ready explanation:""",
        QuestionType.general: """Return a direct technical answer with a simple example if useful.""",
    }

    profile_block = _profile_block(profile)

    return f"""{BASE_SYSTEM}

Question type: {question_type.value}
Default coding language: {language}
{length_instruction}

{profile_block}

Candidate context from resume/projects:
{context or "No candidate-specific context retrieved."}

Use candidate context only when relevant. Do not invent experience or claim work not present in the context.

Required format:
{formats[question_type]}

Question:
{question}
"""
