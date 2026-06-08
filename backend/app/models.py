from enum import Enum
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    coding = "coding"
    aws = "aws"
    system_design = "system_design"
    hr = "hr"
    project = "project"
    concept = "concept"
    general = "general"


class AnswerRequest(BaseModel):
    session_id: str = Field(default="default")
    text: str
    force: bool = False
    mode: str = "normal"
    language: str | None = None


class AnswerResponse(BaseModel):
    session_id: str
    transcript: str
    question: str | None = None
    question_type: QuestionType | None = None
    answer: str | None = None
    should_pause: bool = False
    message: str | None = None


class SessionState(BaseModel):
    transcript: str = ""
    last_question: str | None = None
    last_answer: str | None = None
    language: str = "Python"


class KnowledgeTextRequest(BaseModel):
    title: str = Field(default="profile")
    text: str
    source_type: str = Field(default="profile")


class KnowledgeItem(BaseModel):
    id: str
    title: str
    source_type: str
    preview: str


class KnowledgeIngestResponse(BaseModel):
    status: str
    chunks: int


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeItem]
