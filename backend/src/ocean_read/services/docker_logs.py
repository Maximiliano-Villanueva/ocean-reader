"""Read container logs via Docker Engine API (dev; requires mounted socket)."""

from __future__ import annotations

import docker
from docker.errors import APIError, DockerException, NotFound


def list_project_containers(*, compose_project_name: str) -> list[dict[str, str]]:
    try:
        cli = docker.from_env()
    except DockerException as e:
        raise RuntimeError(f"Cannot reach Docker daemon: {e}") from e

    filt = {"label": [f"com.docker.compose.project={compose_project_name}"]}
    try:
        cs = cli.containers.list(all=True, filters=filt)
    except APIError as e:
        raise RuntimeError(f"Docker API error: {e}") from e

    out: list[dict[str, str]] = []
    for c in sorted(
        cs,
        key=lambda x: (x.labels.get("com.docker.compose.service") or "", x.short_id or ""),
    ):
        nm = c.name or ""
        if nm.startswith("/"):
            nm = nm[1:]
        state = ""
        try:
            state = str((c.attrs or {}).get("State", {}).get("Status", "") or "")
        except (TypeError, AttributeError):
            state = ""
        sid = (c.short_id or "").lstrip("/")
        out.append(
            {
                "id": sid,
                "name": nm,
                "service": c.labels.get("com.docker.compose.service") or "",
                "status": c.status,
                "state": state,
            }
        )
    return out


def tail_container_logs(*, container_id: str, tail: int) -> str:
    tid = container_id.strip().lstrip("/")
    if not tid:
        raise ValueError("missing container id")

    try:
        cli = docker.from_env()
    except DockerException as e:
        raise RuntimeError(f"Cannot reach Docker daemon: {e}") from e

    try:
        cont = cli.containers.get(tid)
    except NotFound as e:
        raise ValueError(f"container not found: {container_id}") from e
    except APIError as e:
        raise RuntimeError(f"Docker API error: {e}") from e

    n = max(1, min(int(tail), 5000))
    try:
        raw = cont.logs(stdout=True, stderr=True, tail=n, timestamps=True)
    except APIError as e:
        raise RuntimeError(f"Docker API error: {e}") from e

    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)
