"""FastAPI app factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.db import init_db
from app.routers import analysis, files, health, issues, projects, revisions
from app.services import dwg_convert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("adv")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting ADV backend v%s", __version__)
    logger.info("  data_dir    = %s", settings.data_dir)
    logger.info("  upload_dir  = %s", settings.upload_dir_abs)
    logger.info("  database    = %s", settings.database_url)
    logger.info("  llm         = %s", settings.llm_provider)
    bin_path = dwg_convert.find_libredwg()
    logger.info(
        "  libredwg    = %s (available=%s)",
        bin_path or "<not found>",
        dwg_convert.libredwg_available(),
    )
    logger.info("  max_insert_expansion = %d", settings.max_insert_expansion)
    init_db()
    yield
    logger.info("Shutting down ADV backend")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ADV — Agentic Drawing Validator",
        version=__version__,
        description=(
            "Mechanical ↔ Structural GA validation. "
            "Reads native DWG/DXF, runs 8 deterministic checks + optional LLM pass."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(analysis.router)
    app.include_router(issues.router)
    app.include_router(revisions.router)
    app.include_router(files.router)

    return app


app = create_app()
