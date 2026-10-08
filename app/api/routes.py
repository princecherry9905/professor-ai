"""JSON API endpoints. HTTP in/out only — the logic lives in TutorService."""

from fastapi import APIRouter, Depends

from app.config.settings import Settings, get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConfigResponse,
    HealthResponse,
    OptionItem,
    QuizEvaluateRequest,
    QuizEvaluation,
    QuizQuestionRequest,
    QuizQuestionResponse,
)
from app.api.dependencies import get_provider, get_tutor_service
from app.prompts.subjects import DEFAULT_SUBJECT, SUBJECTS
from app.providers.base import LLMProvider
from app.services.modes import UI_MODES
from app.services.tutor_service import TutorService

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health", response_model=HealthResponse)
def health(
    provider: LLMProvider = Depends(get_provider), settings: Settings = Depends(get_settings)
) -> HealthResponse:
    if not provider.is_configured:
        status = "not_configured"
    elif provider.auth_failed:
        status = "error"
    else:
        status = "connected"
    return HealthResponse(status="ok", gemini=status, model=settings.gemini_model)


@router.get("/config", response_model=ConfigResponse)
def config(settings: Settings = Depends(get_settings)) -> ConfigResponse:
    return ConfigResponse(
        app_name="ProfessorAI",
        tagline="Your Personal AI College Professor",
        subjects=[OptionItem(id=s.id, name=s.name) for s in SUBJECTS.values()],
        modes=[OptionItem(id=mode_id, name=label) for mode_id, label in UI_MODES],
        default_subject=DEFAULT_SUBJECT,
        default_mode="normal",
        limits={
            "max_question_chars": settings.max_question_chars,
            "max_history_turns": settings.max_history_turns,
            "max_history_text_chars": settings.max_history_text_chars,
        },
        provider=settings.ai_provider,
        model=settings.gemini_model,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, tutor: TutorService = Depends(get_tutor_service)) -> ChatResponse:
    return await tutor.chat(request)


@router.post("/quiz/question", response_model=QuizQuestionResponse)
async def quiz_question(
    request: QuizQuestionRequest, tutor: TutorService = Depends(get_tutor_service)
) -> QuizQuestionResponse:
    return await tutor.quiz_question(request)


@router.post("/quiz/evaluate", response_model=QuizEvaluation)
async def quiz_evaluate(
    request: QuizEvaluateRequest, tutor: TutorService = Depends(get_tutor_service)
) -> QuizEvaluation:
    return await tutor.quiz_evaluate(request)
