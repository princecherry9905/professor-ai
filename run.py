"""Start the ProfessorAI server:  python run.py"""

import uvicorn

from app.config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print(f"\n  ProfessorAI running at http://{settings.host}:{settings.port}\n")
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
