"""Request/response contracts for the API, plus the structured answers we ask the AI for."""

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.config.settings import get_settings
from app.prompts.subjects import SUBJECTS

_settings = get_settings()


class ChatMode(str, Enum):
    normal = "normal"
    one_word = "one_word"
    short = "short"
    detailed = "detailed"
    json = "json"
    professor = "professor"


Difficulty = Literal["easy", "medium", "hard"]


def _validate_subject(value: str) -> str:
    value = value.strip().lower()
    if value not in SUBJECTS:
        raise ValueError(f"Unknown subject '{value}'. Valid: {', '.join(SUBJECTS)}")
    return value


def _validate_text(value: str, limit: int, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if len(value) > limit:
        raise ValueError(f"{field_name} is too long (max {limit} characters)")
    return value


# ---- Chat -------------------------------------------------------------------

class ChatTurn(BaseModel):
    role: Literal["student", "professor"]
    text: str

    @field_validator("text")
    @classmethod
    def check_text(cls, v: str) -> str:
        return _validate_text(v, _settings.max_history_text_chars, "History text")


class ChatRequest(BaseModel):
    question: str
    subject: str = "general"
    mode: ChatMode = ChatMode.normal
    history: list[ChatTurn] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def check_question(cls, v: str) -> str:
        return _validate_text(v, _settings.max_question_chars, "Question")

    @field_validator("subject")
    @classmethod
    def check_subject(cls, v: str) -> str:
        return _validate_subject(v)

    @field_validator("history")
    @classmethod
    def keep_recent_history(cls, v: list[ChatTurn]) -> list[ChatTurn]:
        # Only the most recent turns are useful context; drop older ones quietly.
        return v[-_settings.max_history_turns:]


class JsonAnswer(BaseModel):
    """Fixed schema for JSON mode — always machine-readable."""

    question: str
    topic: str
    answer: str
    explanation: str
    example: str
    difficulty: Difficulty


class ChatResponse(BaseModel):
    answer: Union[str, JsonAnswer]
    mode: ChatMode
    subject: str
    format: Literal["markdown", "text", "json"]


# ---- Quiz -------------------------------------------------------------------

class QuizQuestionRequest(BaseModel):
    subject: str = "general"
    difficulty: Difficulty = "medium"
    topic: Optional[str] = Field(default=None, max_length=200)
    asked: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("subject")
    @classmethod
    def check_subject(cls, v: str) -> str:
        return _validate_subject(v)


class AIQuizQuestion(BaseModel):
    """What we ask the AI to produce for a new quiz question."""

    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    topic: str


class QuizQuestionResponse(BaseModel):
    question_id: str
    question: str
    options: list[str]
    topic: str
    subject: str
    difficulty: Difficulty


class QuizEvaluateRequest(BaseModel):
    subject: str = "general"
    question: str
    options: list[str] = Field(default_factory=list, max_length=6)
    student_answer: str

    @field_validator("subject")
    @classmethod
    def check_subject(cls, v: str) -> str:
        return _validate_subject(v)

    @field_validator("question")
    @classmethod
    def check_question(cls, v: str) -> str:
        return _validate_text(v, _settings.max_question_chars, "Question")

    @field_validator("student_answer")
    @classmethod
    def check_answer(cls, v: str) -> str:
        return _validate_text(v, _settings.max_history_text_chars, "Answer")


class QuizEvaluation(BaseModel):
    correct: bool
    score: int = Field(ge=0, le=10, description="0-10 marks for this answer")
    feedback: str
    model_answer: str


# ---- Health / config --------------------------------------------------------

class HealthResponse(BaseModel):
    status: Literal["ok"]
    gemini: Literal["connected", "not_configured", "error"]
    model: str


class OptionItem(BaseModel):
    id: str
    name: str


class ConfigResponse(BaseModel):
    app_name: str
    tagline: str
    subjects: list[OptionItem]
    modes: list[OptionItem]
    default_subject: str
    default_mode: str
    limits: dict[str, int]
    provider: str
    model: str
