# ProfessorAI

> **Your Personal AI College Professor** — an AI tutor that explains concepts, answers questions,
> quizzes you and adapts to your level. Built with Python, FastAPI and the Google Gemini API.

## 1. Overview

ProfessorAI behaves like a patient college professor rather than a generic chatbot. You pick a
**subject** (DSA, OS, DBMS, CN, OOP, JavaScript, Python, AI, ML, Web Dev, Software Engineering) and a
**response mode**, and the professor answers from that subject's exam perspective.

## 2. Features

- **7 response modes**: Normal, One Word, Short, Detailed, JSON, Professor (step-by-step lesson), Quiz
- **JSON mode always returns valid JSON** with a fixed schema (structured output + validation + one retry)
- **One-word mode** cleans the answer (`"Queue."` → `Queue`, keeps `Many-forms`, `O(log n)`)
- **Quiz mode**: one multiple-choice question at a time, graded out of 10, running score, no repeats
- Subject-aware professor persona that admits uncertainty and teaches rather than dumps answers
- Dark academic UI, responsive for desktop / tablet / mobile, copy buttons, clear chat, Gemini status
- Chat history kept in the browser — no database needed
- Friendly error messages; API key never reaches the browser; no stack traces exposed

## 3. Architecture

```
Browser (HTML + CSS + vanilla JS)
   │  fetch /api/*
   ▼
FastAPI app ── web routes  → index.html + static files
           └── API routes  → Pydantic validation → TutorService
                                   │
          ┌────────────────────────┼─────────────────────────┐
          ▼                        ▼                         ▼
     PromptBuilder            ModeRegistry            ResponseFormatter
  (persona + subject)   (rules per mode, temp,     (one-word cleanup,
                           tokens, JSON schema)       JSON validation)
                                   │
                         LLMProvider (interface)
                                   │
                    GeminiProvider ← only file that imports google-genai
                                   │
                               Gemini API
```

Swapping in OpenAI or Claude later means adding one file in `app/providers/` and setting `AI_PROVIDER`.

## 4. Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI | Google Gemini via the official `google-genai` SDK |
| Validation & config | Pydantic v2 + pydantic-settings + python-dotenv |
| Frontend | Jinja2 template + vanilla JS + hand-written CSS (no build step) |
| Markdown | marked + DOMPurify (bundled in `app/web/static/vendor/`) |
| Tests | pytest + FastAPI TestClient |

## 5. Folder structure

```
professor-ai/
├── app/
│   ├── main.py                    # creates the FastAPI app
│   ├── config/settings.py         # environment variables (typed)
│   ├── api/
│   │   ├── routes.py              # /api/health, /api/config, /api/chat, /api/quiz/*
│   │   ├── web.py                 # serves index.html
│   │   ├── dependencies.py        # picks the AI provider (overridden in tests)
│   │   └── errors.py              # exceptions → friendly JSON errors
│   ├── services/
│   │   ├── tutor_service.py       # orchestrates prompt → model → format → retry
│   │   ├── modes.py               # one ModeSpec per response mode
│   │   └── response_formatter.py  # one-word cleanup, JSON parsing/validation
│   ├── providers/
│   │   ├── base.py                # LLMProvider interface + error types
│   │   └── gemini_provider.py     # the only Gemini-specific code
│   ├── prompts/
│   │   ├── professor_prompt.py    # the professor persona and rules
│   │   └── subjects.py            # subjects + per-subject context
│   ├── models/schemas.py          # request/response models
│   └── web/                       # templates/index.html, static/css, static/js, static/vendor
├── tests/                         # pytest suite with a FakeProvider (no API key needed)
├── .env.example  .gitignore  requirements.txt  pytest.ini  run.py  README.md
```

**Why each folder exists:** `config` — one place for settings · `api` — HTTP layer only ·
`services` — business logic · `providers` — AI vendors, isolated · `prompts` — prompt text kept apart
from code so you can tune the professor without touching logic · `models` — data contracts ·
`web` — the UI · `tests` — the safety net.

## 6. Gemini API setup

1. Go to **Google AI Studio** → <https://aistudio.google.com/apikey> and create a free API key.
2. Copy `.env.example` to `.env` and paste the key:

```bash
cp .env.example .env        # Windows: copy .env.example .env
# then edit .env:
GEMINI_API_KEY=AIza...your-key...
```

`.env` is in `.gitignore` — never commit it.

## 7. Environment variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(none)* | Your Gemini key. Without it the app still starts and shows "API key not set". |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Any Gemini model name your key can use. |
| `AI_PROVIDER` | `gemini` | Which provider to use (extension point). |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Timeout for each Gemini call. |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Where the server listens. |

## 8. Installation

Requires **Python 3.10+**.

```bash
cd professor-ai
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env   # then add your key
```

## 9. Running the application

```bash
python run.py
```

Open **http://127.0.0.1:8000**. Interactive API docs are at **http://127.0.0.1:8000/docs**.

## 10. API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{status, gemini: "connected" \| "not_configured" \| "error", model}` |
| GET | `/api/config` | Subjects, modes and input limits (no secrets) |
| POST | `/api/chat` | Main tutor endpoint for all modes except Quiz |
| POST | `/api/quiz/question` | Generate one multiple-choice question |
| POST | `/api/quiz/evaluate` | Grade the student's answer (0–10) |

Modes for `/api/chat`: `normal`, `one_word`, `short`, `detailed`, `json`, `professor`.

## 11. Example requests

```bash
curl -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" \
  -d '{"question": "Which data structure follows FIFO?", "subject": "dsa", "mode": "one_word"}'

curl -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" \
  -d '{"question": "What is HTTP?", "subject": "cn", "mode": "json",
       "history": [{"role": "student", "text": "Hi"}, {"role": "professor", "text": "Hello!"}]}'

curl -X POST http://127.0.0.1:8000/api/quiz/question -H "Content-Type: application/json" \
  -d '{"subject": "dbms", "difficulty": "medium", "asked": []}'
```

## 12. Example responses

```json
{ "answer": "Queue", "mode": "one_word", "subject": "dsa", "format": "text" }
```

```json
{
  "answer": {
    "question": "What is HTTP?",
    "topic": "Application layer protocols",
    "answer": "A request/response protocol for communication between web clients and servers.",
    "explanation": "The client sends a request (method, path, headers) and the server replies with a status code and body.",
    "example": "GET /index.html → 200 OK",
    "difficulty": "easy"
  },
  "mode": "json", "subject": "cn", "format": "json"
}
```

Errors always look like this (no stack traces):

```json
{ "error": { "code": "RATE_LIMITED", "message": "Professor is busy right now. Please try again in a moment." } }
```

| Code | HTTP |
|---|---|
| `VALIDATION_ERROR` | 422 |
| `API_KEY_MISSING` / `API_KEY_INVALID` | 503 |
| `RATE_LIMITED` | 429 |
| `TIMEOUT` | 504 |
| `PROVIDER_UNAVAILABLE` / `INVALID_AI_RESPONSE` | 502 |
| `INTERNAL_ERROR` | 500 |

## 13. Testing

```bash
pytest
```

The suite (86 tests) uses a `FakeProvider`, so **no API key or internet is needed**. It covers the
health/config endpoints, request validation (empty, oversized, unknown subject/mode), every response
mode, JSON validity and retry, quiz endpoints, Gemini error mapping and retry rules, and the
missing-key path.

After adding your key, do a quick manual check: ask one question in each mode in the browser.

## 14. Future improvements

The architecture leaves room for these without rewrites:

- **Conversation memory / PostgreSQL** — add a `ConversationRepository`; the API already accepts `history`
- **Multiple AI providers** — new file in `app/providers/` + `AI_PROVIDER`
- **RAG, PDF upload, college notes** — a `ContextRetriever` step in `TutorService` before prompt building
- **Flashcards, MCQ sets, exam prep** — new `ModeSpec`s or endpoints reusing `TutorService`
- **Auth, progress tracking, study planner** — new routers + repositories
- **Voice input / text-to-speech** — frontend Web Speech API

## Known limitations

- Chat history lives in your browser's localStorage; it's per-browser and not synced.
- Quiz score resets when you reload or switch subject.
- One-word mode keeps only the first term; truly multi-word answers get shortened.
- Model output can still be wrong — the professor is told to admit uncertainty, but double-check facts for exams.
- No per-IP rate limiting (fine for local use; add one before deploying publicly).
