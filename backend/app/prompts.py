from .models import QuestionType


BASE_SYSTEM = """You are a silent interview copilot displayed on a phone.
Generate concise, interview-ready notes the candidate can speak naturally.
Do not mention that you are an AI. Avoid long essays. Prefer direct bullets.
If the question is ambiguous, give a practical answer with assumptions."""


def build_prompt(question: str, question_type: QuestionType, mode: str = "normal") -> str:
    length_instruction = {
        "short": "Keep the answer very short: 3-5 bullets max.",
        "regenerate": "Provide an alternative answer with a different wording.",
    }.get(mode, "Keep the answer compact but complete.")

    formats = {
        QuestionType.coding: """Return:
Approach:
Code: use Python unless the question asks otherwise
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

    return f"""{BASE_SYSTEM}

Question type: {question_type.value}
{length_instruction}

Required format:
{formats[question_type]}

Question:
{question}
"""
