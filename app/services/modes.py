"""Response modes. Each mode is one ModeSpec — adding a mode means adding one entry."""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from app.models.schemas import ChatMode, JsonAnswer

OutputFormat = Literal["markdown", "text", "one_word", "json"]


@dataclass(frozen=True)
class ModeSpec:
    id: str
    label: str
    instruction: str
    temperature: float
    max_output_tokens: int
    output_format: OutputFormat
    json_schema: Optional[Dict[str, Any]] = None


def schema_for_model(model: type) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    return schema


JSON_ANSWER_SCHEMA = schema_for_model(JsonAnswer)

MODES: dict[ChatMode, ModeSpec] = {
    ChatMode.normal: ModeSpec(
        id="normal",
        label="Normal",
        instruction=(
            "Give a clear, natural educational explanation. Start with the simple idea, then add "
            "the important details and one example. Keep it focused; no padding."
        ),
        temperature=0.6,
        max_output_tokens=2048,
        output_format="markdown",
    ),
    ChatMode.one_word: ModeSpec(
        id="one_word",
        label="One Word",
        instruction=(
            "Reply with ONLY the single word or shortest standard term that answers the question "
            "(e.g. 'Queue', 'Many-forms', 'O(log n)'). No sentence, no explanation, no punctuation, "
            "no Markdown, no quotes."
        ),
        temperature=0.1,
        max_output_tokens=64,
        output_format="one_word",
    ),
    ChatMode.short: ModeSpec(
        id="short",
        label="Short",
        instruction=(
            "Answer in 1 to 3 plain sentences. No headings, no bullet lists, no code blocks "
            "unless the question is literally asking for a tiny code snippet."
        ),
        temperature=0.4,
        max_output_tokens=400,
        output_format="text",
    ),
    ChatMode.detailed: ModeSpec(
        id="detailed",
        label="Detailed",
        instruction=(
            "Answer using EXACTLY these Markdown headings, in this order:\n"
            "## Definition\n## Explanation\n## Example\n## Important Points\n## Exam Tip\n"
            "Under 'Important Points' use a bullet list. Use code blocks for code examples."
        ),
        temperature=0.5,
        max_output_tokens=3072,
        output_format="markdown",
    ),
    ChatMode.json: ModeSpec(
        id="json",
        label="JSON",
        instruction=(
            "Return ONLY a JSON object, with no Markdown, no code fences and no text before or "
            "after it. Use exactly these keys: question (the student's question restated), topic, "
            "answer (concise), explanation, example, difficulty (one of: easy, medium, hard)."
        ),
        temperature=0.2,
        max_output_tokens=2048,
        output_format="json",
        json_schema=JSON_ANSWER_SCHEMA,
    ),
    ChatMode.professor: ModeSpec(
        id="professor",
        label="Professor",
        instruction=(
            "Teach this as a short live lesson, step by step, like a professor in class:\n"
            "1. Start with intuition or a real-world analogy.\n"
            "2. Build the concept in small numbered steps.\n"
            "3. Work through one example (with a dry run for code).\n"
            "4. Point out a common mistake students make.\n"
            "5. End with ONE short question that checks the student's understanding "
            "(do not answer it)."
        ),
        temperature=0.6,
        max_output_tokens=3072,
        output_format="markdown",
    ),
}

# Shown in the UI. Quiz uses its own endpoints, not /api/chat.
UI_MODES: list[tuple[str, str]] = [(spec.id, spec.label) for spec in MODES.values()] + [
    ("quiz", "Quiz")
]

STRICT_JSON_RETRY_INSTRUCTION = (
    "Your previous reply was not valid JSON matching the required keys. Reply again with ONLY "
    "one raw JSON object (starting with '{' and ending with '}') and nothing else."
)
