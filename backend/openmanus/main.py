from __future__ import annotations

import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
import sys

if hasattr(sys, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from openmanus.agents import AGENTS_DIR, agent_loader
from openmanus.agents.avatar import AVATARS_SEED_DIR
from openmanus.agents.routers import router as agents_router
from openmanus.config import settings
from openmanus.db import init_db
from openmanus.log import logger
from openmanus.sandbox.routers import router as sandbox_router
from openmanus.skills.loader import skill_loader
from openmanus.skills.routers import router as skills_router
from openmanus.tools.routers import router as tools_router
from openmanus.tools.tool_loader import tool_loader
from openmanus.topics.routers import router as topics_router
from openmanus.topics.session_routers import router as sessions_router
from openmanus.topics.store import topic_store
from openmanus.runtime.routers import router as streams_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    agent_loader.seed_builtin()
    agent_loader.load_all()
    logger.info("loaded %d agents from %s", len(agent_loader.configs), agent_loader.dir)

    tool_loader.load_all()
    if tool_loader.all_names():
        logger.info(
            "loaded %d user tools from %s: %s",
            len(tool_loader.all_names()), tool_loader.dir, tool_loader.all_names(),
        )

    skill_loader.load_all()
    if skill_loader.all_names():
        logger.info(
            "loaded %d skills from %s: %s",
            len(skill_loader.all_names()), skill_loader.dir, skill_loader.all_names(),
        )

    await init_db()
    main_topic = await topic_store.ensure_main()
    if main_topic and main_topic.workdir:
        settings.workdir = main_topic.workdir
    logger.info(
        "openmanus ready | model=%s base=%s workdir=%s db=%s",
        settings.model, settings.openai_base_url, settings.workdir, settings.database_url,
    )
    yield

def create_app() -> FastAPI:
    app = FastAPI(title="openmanus", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(streams_router)
    app.include_router(sessions_router)
    app.include_router(topics_router)
    app.include_router(agents_router)
    app.include_router(skills_router)
    app.include_router(tools_router)
    app.include_router(sandbox_router)

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/agent-assets", StaticFiles(directory=str(AGENTS_DIR)), name="agent-assets")

    AVATARS_SEED_DIR.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/avatar-presets",
        StaticFiles(directory=str(AVATARS_SEED_DIR)),
        name="avatar-presets",
    )

    return app

app = create_app()
