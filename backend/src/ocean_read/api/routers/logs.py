"""Docker log viewer API (Compose project containers)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from ocean_read.config import get_settings
from ocean_read.schemas import LogViewerContainerRead, LogViewerTailRead
from ocean_read.services.docker_logs import list_project_containers, tail_container_logs

router = APIRouter(tags=["Logs"])


def require_log_viewer(
    x_log_viewer_token: str | None = Header(default=None, alias="X-Log-Viewer-Token"),
) -> None:
    cfg = get_settings()
    if not cfg.log_viewer_enabled:
        raise HTTPException(status_code=404, detail="Log viewer is disabled")
    if cfg.log_viewer_token.strip():
        if (x_log_viewer_token or "").strip() != cfg.log_viewer_token.strip():
            raise HTTPException(status_code=401, detail="Invalid or missing X-Log-Viewer-Token")


@router.get("/logs/containers", response_model=list[LogViewerContainerRead])
async def logs_list_containers(_: None = Depends(require_log_viewer)) -> list[LogViewerContainerRead]:
    cfg = get_settings()
    try:
        rows = await run_in_threadpool(
            list_project_containers,
            compose_project_name=cfg.compose_project_name,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return [LogViewerContainerRead(**r) for r in rows]


@router.get("/logs/containers/{container_id}/tail", response_model=LogViewerTailRead)
async def logs_tail(
    container_id: str,
    _: None = Depends(require_log_viewer),
    tail: int = Query(default=400, ge=1, le=5000),
) -> LogViewerTailRead:
    cid = container_id.strip()
    try:
        text = await run_in_threadpool(
            tail_container_logs,
            container_id=cid,
            tail=tail,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return LogViewerTailRead(container_id=cid, tail=tail, text=text)
