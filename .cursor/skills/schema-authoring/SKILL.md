---
name: schema-authoring
description: Guide for the ADK schema authoring agent, DSL v3 open_ended fields, and vLLM compose profile. Use when changing schema agent, open-ended extraction, or SCHEMA_AGENT docs.
---

# Schema authoring (ADK + vLLM)

## Layout

| Area | Path |
|------|------|
| Agent service | `schema_agent/` — see `AGENTS.md` |
| DSL validation | `backend/.../schema_dsl.py` |
| Open-ended runtime | `open_ended_runner.py`, `validation_pipeline.py` |
| Frontend workspace | `SchemaAuthoringWorkspace.tsx`, Assistant tab |
| Docs | `docs/implementation/SCHEMA_AGENT.md`, ADR 004 |

## Rules

1. Strict `fields` → deterministic engine only; never LLM PASS/FAIL.
2. `open_ended` → version `"3"`; `informative_only` vs `evaluate_prompt` + tags.
3. Human edits JSON anytime; agent receives full `CURRENT_SCHEMA_JSON` each chat.
4. Do not remove Ollama until vLLM path is production-stable.
5. Deferred: chat persistence, MCP/A2A, multimodal PDF to model.

## Run LLM stack

```bash
ollama pull gemma4:e4b && ./start.sh
./scripts/verify_docker_llm.sh
```

## Tests

- Default CI: `pytest` (mocks, no vLLM).
- Live: `pytest -m llm` with stack up.
