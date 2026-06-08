import re
from .models import QuestionType


QUESTION_STARTERS = (
    "what", "why", "how", "when", "where", "which", "who",
    "can you", "could you", "would you", "do you", "did you",
    "explain", "describe", "tell me", "walk me through", "design",
    "implement", "write", "solve", "difference between", "need",
    "give", "create", "build", "find",
)

TASK_STARTERS = (
    "need", "give", "create", "build", "find", "write", "implement",
    "solve", "design", "explain", "describe", "tell", "show",
)

CODING_HINTS = (
    "code", "program", "function", "algorithm", "array", "string", "linked list",
    "tree", "graph", "stack", "queue", "hashmap", "dictionary", "fibonacci",
    "palindrome", "reverse", "duplicates", "sort", "search", "complexity",
    "big o", "python", "java", "leetcode",
)

AWS_HINTS = (
    "aws", "ec2", "vpc", "s3", "lambda", "alb", "nlb", "elb", "iam",
    "cloudwatch", "cloudfront", "route 53", "rds", "dynamodb", "autoscaling",
    "auto scaling", "eks", "ecs", "security group", "subnet", "nat gateway",
)

DESIGN_HINTS = (
    "system design", "design a", "design an", "architecture", "scale",
    "scalable", "url shortener", "notification service", "rate limiter",
    "high availability", "load balancer", "database choice", "throughput",
)

HR_HINTS = (
    "tell me about yourself", "why should we hire", "why are you leaving",
    "strength", "weakness", "conflict", "challenge", "salary", "relocate",
    "notice period", "current company", "career goal",
)

PROJECT_HINTS = (
    "aiops", "opsmitra", "your project", "your platform", "subtitle generator",
    "resume", "previous project", "recent project", "walk me through your project",
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def is_question_like(text: str) -> bool:
    lowered = normalize(text).lower()
    if not lowered:
        return False
    if lowered.endswith("?"):
        return True
    return any(lowered.startswith(prefix) for prefix in QUESTION_STARTERS) or any(
        phrase in lowered for phrase in (
            "difference between", "how would you", "what happens if",
            "can you explain", "could you explain", "walk me through",
            "need python code", "need code", "give code", "write code",
            "find duplicates", "reverse a string", "check palindrome",
            "design url shortener",
        )
    )


def is_interview_task(text: str) -> bool:
    lowered = normalize(text).lower()
    if is_question_like(lowered):
        return True
    if any(lowered.startswith(prefix) for prefix in TASK_STARTERS):
        return any(
            hint in lowered
            for hint in CODING_HINTS + AWS_HINTS + DESIGN_HINTS + HR_HINTS + PROJECT_HINTS
        )
    return False


def is_complete_enough(text: str) -> bool:
    lowered = normalize(text).lower()
    if len(lowered.split()) < 3:
        return False
    incomplete_endings = (
        "and", "or", "but", "with", "for", "to", "between", "where",
        "when", "if", "that", "which", "like", "using",
    )
    return not lowered.endswith(incomplete_endings)


def classify_question(text: str) -> QuestionType:
    lowered = normalize(text).lower()

    def has_any(hints: tuple[str, ...]) -> bool:
        return any(hint in lowered for hint in hints)

    if has_any(CODING_HINTS):
        return QuestionType.coding
    if has_any(AWS_HINTS):
        return QuestionType.aws
    if has_any(DESIGN_HINTS):
        return QuestionType.system_design
    if has_any(HR_HINTS):
        return QuestionType.hr
    if has_any(PROJECT_HINTS):
        return QuestionType.project
    if is_question_like(lowered):
        return QuestionType.concept
    return QuestionType.general


def extract_recent_question(transcript: str) -> str | None:
    text = normalize(transcript)
    if not text:
        return None

    chunks = re.split(r"(?<=[?.!])\s+", text)
    candidates = [chunk for chunk in chunks[-4:] if is_interview_task(chunk)]
    if candidates:
        return normalize(candidates[-1])

    words = text.split()
    tail = " ".join(words[-50:])
    if is_interview_task(tail):
        return normalize(tail)
    return None
