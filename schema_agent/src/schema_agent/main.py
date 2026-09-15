"""
FastAPI entrypoint for the schema authoring agent service.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from schema_agent.agent_runner import SchemaAgentRunner
from schema_agent.ollama_probe import ollama_ready

app = FastAPI(title="Ocean Read Schema Agent", version="0.1.0")
_runner: SchemaAgentRunner | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class SchemaAgentValidationFeedback(BaseModel):
    dsl_ok: bool = True
    dsl_errors: list[str] = Field(default_factory=list)
    preview_status: str | None = None
    preview_summary: str | None = None


class SchemaAgentChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    schema_body: dict[str, Any] = Field(default_factory=dict)
    sample_pdf_note: str | None = Field(
        default=None,
        description="Optional note when user attached a sample PDF (text summary, not bytes yet).",
    )
    validation_feedback: SchemaAgentValidationFeedback | None = None


class SchemaAgentChatResponse(BaseModel):
    reply: str
    schema_body: dict[str, Any]


@app.on_event("startup")
async def _startup() -> None:
    global _runner
    _runner = SchemaAgentRunner()


@app.get("/health")
async def health() -> dict[str, str]:
    ok, detail = ollama_ready()
    if not ok:
        raise HTTPException(503, f"Ollama not ready: {detail}")
    return {"status": "ok", "ollama": detail}


@app.post("/chat", response_model=SchemaAgentChatResponse)
async def chat(req: SchemaAgentChatRequest) -> SchemaAgentChatResponse:
    if _runner is None:
        raise HTTPException(503, "Agent not ready")
    try:
        vf = req.validation_feedback.model_dump() if req.validation_feedback else None
        out = await _runner.chat(
            messages=[m.model_dump() for m in req.messages],
            schema_body=req.schema_body,
            sample_pdf_note=req.sample_pdf_note,
            validation_feedback=vf,
        )
    except Exception as exc:
        msg = str(exc).strip() or exc.__class__.__name__
        if (
            "Connection error" in msg
            or "cannot reach Ollama" in msg
            or "Ollama chat failed" in msg
            or "Ollama" in msg
        ):
            model = os.environ.get("LLM_MODEL", "gemma4:e4b")
            raise HTTPException(
                503,
                f"Language model (Ollama) is not reachable. Start Ollama on the host and run: ollama pull {model}",
            ) from exc
        raise HTTPException(502, f"Agent error: {msg}") from exc
    return SchemaAgentChatResponse(**out)
