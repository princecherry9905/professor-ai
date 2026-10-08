"""ResponseFormatter unit tests."""

import pytest

from app.models.schemas import JsonAnswer
from app.services.response_formatter import (
    InvalidAIResponse,
    format_one_word,
    format_text,
    parse_json_model,
)

GOOD = ('{"question": "q", "topic": "t", "answer": "a", "explanation": "e", '
        '"example": "x", "difficulty": "medium"}')


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Queue", "Queue"), ("Queue.", "Queue"), ("  queue!\n", "queue"),
        ('"Stack"', "Stack"), ("`Heap`", "Heap"), ("**Many-forms**", "Many-forms"),
        ("Many-forms.", "Many-forms"), ("The answer is: Recursion", "Recursion"),
        ("Encapsulation is the answer", "Encapsulation"), ("O(n log n)", "O(n log n)"),
    ],
)
def test_one_word_cleanup(raw, expected):
    assert format_one_word(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\n\n", "...", "**"])
def test_one_word_rejects_empty(raw):
    with pytest.raises(InvalidAIResponse):
        format_one_word(raw)


def test_format_text_strips_and_rejects_empty():
    assert format_text("  hello \n") == "hello"
    with pytest.raises(InvalidAIResponse):
        format_text("   ")


@pytest.mark.parametrize(
    "raw",
    [GOOD, f"```json\n{GOOD}\n```", f"```\n{GOOD}\n```", f"Here is your JSON:\n{GOOD}\nHope it helps!"],
)
def test_parse_json_variants(raw):
    assert parse_json_model(raw, JsonAnswer).answer == "a"


@pytest.mark.parametrize(
    "raw",
    ["not json at all", "[1, 2, 3]", '{"question": "q"}', "{broken json",
     GOOD.replace('"medium"', '"expert"')],
)
def test_parse_json_invalid(raw):
    with pytest.raises(InvalidAIResponse):
        parse_json_model(raw, JsonAnswer)
