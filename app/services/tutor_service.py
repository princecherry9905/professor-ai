"""Orchestrates a tutoring request: build prompt -> call model -> format -> retry if needed.

This file knows nothing about Gemini; it only talks to the LLMProvider interface.
"""

import logging
import uuid
from typing import TypeVar, Union

from pydantic import BaseModel

from app.models.schemas import (
    AIQuizQuestion,
    ChatMode,
    ChatRequest,
    ChatResponse,
    JsonAnswer,
    QuizEvaluateRequest,
    QuizEvaluation,
    QuizQuestionRequest,
    QuizQuestionResponse,
)
from app.prompts.professor_prompt import build_system_prompt
from app.prompts.subjects import SUBJECTS
from app.providers.base import GenerationConfig, LLMProvider, Message
from app.services import response_formatter as fmt
from app.services.modes import MODES, STRICT_JSON_RETRY_INSTRUCTION, ModeSpec, schema_for_model

logger = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

QUIZ_QUESTION_INSTRUCTION = """\
You are setting ONE multiple-choice quiz question for the student.
- Difficulty: {difficulty}.
- {topic_line}
- Exactly 4 options, exactly one correct. Options are plain text WITHOUT letters like "A)".
- Do NOT repeat or closely paraphrase any of these previously asked questions:
{asked}
Return ONLY a JSON object with keys: question, options (array of 4 strings), topic.
Do not reveal the correct answer."""

QUIZ_EVALUATE_INSTRUCTION = """\
You are grading the student's answer to a quiz question, as a fair but strict professor.
Decide if the answer is correct, give a score from 0 to 10, short encouraging feedback that
explains WHY it is right or wrong, and the model (correct) answer.
If options are given, the student may answer with the option text or its letter (A-D, in order).
Return ONLY a JSON object with keys: correct (boolean), score (integer 0-10), feedback, model_answer."""


class TutorService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    # ---- Chat ---------------------------------------------------------------

    async def chat(self, request: ChatRequest) -> ChatResponse:
        spec = MODES[request.mode]
        system = build_system_prompt(SUBJECTS[request.subject], spec.instruction)
        messages = [Message(role=t.role, text=t.text) for t in request.history]
        messages.append(Message(role="student", text=request.question))
        config = GenerationConfig(
            temperature=spec.temperature,
            max_output_tokens=spec.max_output_tokens,
            json_schema=spec.json_schema,
        )

        if spec.output_format == "json":
            answer: Union[str, JsonAnswer] = await self._generate_json(system, messages, config, JsonAnswer)
            response_format = "json"
        else:
            raw = await self._provider.generate(system, messages, config)
            answer = self._format_text_answer(raw, spec)
            response_format = "markdown" if spec.output_format == "markdown" else "text"

        return ChatResponse(
            answer=answer, mode=request.mode, subject=request.subject, format=response_format
        )

    @staticmethod
    def _format_text_answer(raw: str, spec: ModeSpec) -> str:
        if spec.output_format == "one_word":
            return fmt.format_one_word(raw)
        return fmt.format_text(raw)

    # ---- Quiz ---------------------------------------------------------------

    async def quiz_question(self, request: QuizQuestionRequest) -> QuizQuestionResponse:
        subject = SUBJECTS[request.subject]
        asked = "\n".join(f"  - {q}" for q in request.asked[-20:]) or "  (none yet)"
        topic_line = (
            f"Focus on this topic: {request.topic}." if request.topic else
            f"Pick any important exam topic from {subject.name}."
        )
        instruction = QUIZ_QUESTION_INSTRUCTION.format(
            difficulty=request.difficulty, topic_line=topic_line, asked=asked
        )
        system = build_system_prompt(subject, instruction)
        config = GenerationConfig(
            temperature=0.8, max_output_tokens=1024,
            json_schema=schema_for_model(AIQuizQuestion),
        )
        messages = [Message(role="student", text="Give me the next quiz question, please.")]
        q = await self._generate_json(system, messages, config, AIQuizQuestion)
        return QuizQuestionResponse(
            question_id=uuid.uuid4().hex[:12],
            question=q.question,
            options=q.options,
            topic=q.topic,
            subject=request.subject,
            difficulty=request.difficulty,
        )

    async def quiz_evaluate(self, request: QuizEvaluateRequest) -> QuizEvaluation:
        system = build_system_prompt(SUBJECTS[request.subject], QUIZ_EVALUATE_INSTRUCTION)
        options = "\n".join(f"{chr(65 + i)}. {o}" for i, o in enumerate(request.options))
        prompt = (
            f"Question: {request.question}\n"
            + (f"Options:\n{options}\n" if options else "")
            + f"Student's answer: {request.student_answer}"
        )
        config = GenerationConfig(
            temperature=0.2, max_output_tokens=1024,
            json_schema=schema_for_model(QuizEvaluation),
        )
        return await self._generate_json(
            system, [Message(role="student", text=prompt)], config, QuizEvaluation
        )

    # ---- Shared JSON helper -------------------------------------------------

    async def _generate_json(
        self, system: str, messages: list[Message], config: GenerationConfig, model: type[M]
    ) -> M:
        """Ask for JSON, validate it, retry once with a stricter instruction, else raise."""
        raw = await self._provider.generate(system, messages, config)
        try:
            return fmt.parse_json_model(raw, model)
        except fmt.InvalidAIResponse as first_error:
            logger.warning("Invalid JSON from model, retrying once: %s", first_error)

        stricter = GenerationConfig(
            temperature=0.0, max_output_tokens=config.max_output_tokens, json_schema=config.json_schema
        )
        raw = await self._provider.generate(f"{system}\n{STRICT_JSON_RETRY_INSTRUCTION}", messages, stricter)
        return fmt.parse_json_model(raw, model)  # raises InvalidAIResponse if still bad
