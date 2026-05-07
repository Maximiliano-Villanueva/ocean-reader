"""Application entry."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from ocean_read.api.routes import router as api_router
from ocean_read.domain.exceptions import ProjectNotFound


@asynccontextmanager
async def _lifespan(_: FastAPI):
    """Ensure ``ocean_read`` INFO logs are visible under uvicorn."""
    pkg = logging.getLogger("ocean_read")
    pkg.setLevel(logging.INFO)
    if not pkg.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        pkg.addHandler(handler)
    pkg.propagate = False
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=_lifespan,
        title="Ocean Read API",
        version="0.1.0",
        openapi_tags=[
            {"name": "System", "description": "Health checks"},
            {"name": "Workspace", "description": "Projects"},
            {"name": "Validation", "description": "Schema-driven PDF validation"},
            {"name": "Logs", "description": "Compose container logs via Docker socket (dev)"},
        ],
    )

    @app.exception_handler(ProjectNotFound)
    async def _project_not_found(_: Request, __: ProjectNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "ocean-read", "docs": "/docs"}

    return app


app = create_app()
