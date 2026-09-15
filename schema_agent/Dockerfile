FROM python:3.12-slim

WORKDIR /app

COPY schema_agent/pyproject.toml /app/pyproject.toml
COPY schema_agent/src /app/src
RUN pip install --no-cache-dir /app

ENV PYTHONPATH=/app/src
EXPOSE 8081

CMD ["uvicorn", "schema_agent.main:app", "--host", "0.0.0.0", "--port", "8081"]
