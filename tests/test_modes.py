"""Each response mode end-to-end through /api/chat, plus the quiz endpoints."""

import json

import pytest

VALID_JSON = {
    "question": "What is HTTP?", "topic": "Networking",
    "answer": "A protocol for web communication.", "explanation": "Request/response over TCP.",
    "example": "GET /index.html", "difficulty": "easy",
}


def chat(client, mode, question="What is polymorphism?", subject="oop"):
    return client.post("/api/chat", json={"question": question, "subject": subject, "mode": mode})


@pytest.mark.parametrize(
    "mode, reply, expected_format",
    [
        ("normal", "Polymorphism means many forms.", "markdown"),
        ("short", "Polymorphism lets one interface have many implementations.", "text"),
        ("detailed", "## Definition\n...\n## Exam Tip\n...", "markdown"),
        ("professor", "Step 1 ... What do you think happens?", "markdown"),
    ],
)
def test_text_modes(client, fake, mode, reply, expected_format):
    fake.replies = [reply]
    res = chat(client, mode)
    assert res.status_code == 200
    assert res.json()["format"] == expected_format
    assert res.json()["answer"] == reply


def test_each_mode_uses_its_own_settings(client, fake):
    fake.replies = ["Queue"]
    chat(client, "one_word")
    config = fake.calls[0]["config"]
    assert config.temperature == 0.1
    assert config.json_schema is None
    assert "ONLY the single word" in fake.calls[0]["system"]


@pytest.mark.parametrize(
    "reply, expected",
    [("Queue.", "Queue"), ("**Many-forms**", "Many-forms"), ("Answer: Stack", "Stack"),
     ("O(log n)", "O(log n)"), ("Queue\n\nBecause FIFO.", "Queue")],
)
def test_one_word_mode(client, fake, reply, expected):
    fake.replies = [reply]
    res = chat(client, "one_word", question="Which data structure follows FIFO?", subject="dsa")
    assert res.status_code == 200
    assert res.json()["answer"] == expected
    assert res.json()["format"] == "text"


def test_json_mode_returns_real_object(client, fake):
    fake.replies = [json.dumps(VALID_JSON)]
    res = chat(client, "json", question="What is HTTP?", subject="cn")
    assert res.status_code == 200
    body = res.json()
    assert body["format"] == "json"
    assert body["answer"] == VALID_JSON          # an object, not a string
    assert fake.calls[0]["config"].json_schema["required"]  # structured output requested


def test_json_mode_accepts_fenced_json(client, fake):
    fake.replies = ["```json\n" + json.dumps(VALID_JSON) + "\n```"]
    assert chat(client, "json").json()["answer"] == VALID_JSON


def test_json_mode_retries_once_then_succeeds(client, fake):
    fake.replies = ["Here is your JSON: oops", json.dumps(VALID_JSON)]
    res = chat(client, "json")
    assert res.status_code == 200
    assert len(fake.calls) == 2
    assert "not valid JSON" in fake.calls[1]["system"]
    assert fake.calls[1]["config"].temperature == 0.0


def test_json_mode_never_returns_broken_json(client, fake):
    fake.replies = ["not json", '{"topic": "missing keys"}']
    res = chat(client, "json")
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "INVALID_AI_RESPONSE"
    json.loads(res.text)  # the error itself is valid JSON


def test_json_mode_rejects_bad_difficulty(client, fake):
    bad = dict(VALID_JSON, difficulty="impossible")
    fake.replies = [json.dumps(bad), json.dumps(bad)]
    assert chat(client, "json").status_code == 502


# ---- Quiz -------------------------------------------------------------------

QUESTION = {"question": "Which structure is LIFO?", "options": ["Queue", "Stack", "Heap", "Graph"], "topic": "Stacks"}


def test_quiz_question(client, fake):
    fake.replies = [json.dumps(QUESTION)]
    res = client.post("/api/quiz/question", json={
        "subject": "dsa", "difficulty": "easy", "asked": ["What is a queue?"]})
    assert res.status_code == 200
    body = res.json()
    assert body["question"] == QUESTION["question"]
    assert body["options"] == QUESTION["options"]
    assert body["difficulty"] == "easy" and body["question_id"]
    assert "What is a queue?" in fake.calls[0]["system"]  # avoids repeats


def test_quiz_question_needs_four_options(client, fake):
    bad = dict(QUESTION, options=["Only", "Three", "Options"])
    fake.replies = [json.dumps(bad), json.dumps(bad)]
    assert client.post("/api/quiz/question", json={"subject": "dsa"}).status_code == 502


def test_quiz_evaluate(client, fake):
    fake.replies = [json.dumps({"correct": True, "score": 10, "feedback": "Well done.", "model_answer": "Stack"})]
    res = client.post("/api/quiz/evaluate", json={
        "subject": "dsa", "question": QUESTION["question"], "options": QUESTION["options"],
        "student_answer": "B"})
    assert res.status_code == 200
    assert res.json()["correct"] is True and res.json()["score"] == 10
    prompt = fake.calls[0]["messages"][0].text
    assert "B. Stack" in prompt and "Student's answer: B" in prompt


def test_quiz_evaluate_empty_answer_rejected(client):
    res = client.post("/api/quiz/evaluate", json={"subject": "dsa", "question": "Q?", "student_answer": " "})
    assert res.status_code == 422


def test_quiz_invalid_difficulty_rejected(client):
    assert client.post("/api/quiz/question", json={"subject": "dsa", "difficulty": "extreme"}).status_code == 422
