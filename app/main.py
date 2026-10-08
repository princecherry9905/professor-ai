"""Creates the FastAPI app: API routes, web page, static files, error handlers."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import routes, web
from app.api.errors import register_error_handlers

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ProfessorAI",
        description="Your Personal AI College Professor — powered by Google Gemini.",
        version="1.0.0",
    )
    register_error_handlers(app)
    app.include_router(routes.router)
    app.include_router(web.router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app


app = create_app()
