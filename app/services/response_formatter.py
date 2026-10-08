"""Cleans raw model output so each mode returns exactly what it promises."""

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)

_WRAPPING_CHARS = "\"'`*_ \t"
_EDGE_PUNCTUATION = ".,;:!?\"'`*_“”‘’"
_CODE_FENCE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


class InvalidAIResponse(Exception):
    """The model's reply could not be turned into the required format."""


def format_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise InvalidAIResponse("Empty answer")
    return text


def format_one_word(raw: str) -> str:
    """'Queue.' -> 'Queue', '**Many-forms**' -> 'Many-forms', 'O(log n)' kept whole."""
    lines = [line for line in raw.strip().splitlines() if line.strip()]
    if not lines:
        raise InvalidAIResponse("Empty one-word answer")

    first_line = lines[0].strip().strip(_WRAPPING_CHARS)
    first_line = re.sub(r"^(answer|the answer is)\s*[:\-]\s*", "", first_line, flags=re.IGNORECASE)
    first_line = first_line.strip(_EDGE_PUNCTUATION + " ")

    # Short notations with brackets, like "O(log n)", are one "term" even with a space.
    if "(" in first_line and ")" in first_line and len(first_line) <= 20:
        return first_line

    word = first_line.split()[0] if first_line.split() else ""
    word = word.strip(_EDGE_PUNCTUATION)
    if not word:
        raise InvalidAIResponse("Could not extract a single word")
    return word


def parse_json_model(raw: str, model: type[M]) -> M:
    """Parse model output into a validated Pydantic object, tolerating code fences."""
    text = raw.strip()
    fenced = _CODE_FENCE.match(text)
    if fenced:
        text = fenced.group(1).strip()

    data = _loads_object(text)
    if data is None:
        raise InvalidAIResponse("Reply was not a JSON object")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise InvalidAIResponse(f"JSON did not match schema: {exc.error_count()} error(s)") from exc


def _loads_object(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} block if the model added stray text.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
