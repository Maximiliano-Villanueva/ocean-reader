FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic alembic
COPY alembic.ini .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src
ENV UPLOAD_ROOT=/data/uploads

RUN mkdir -p /data/uploads

EXPOSE 8000

CMD sh -c "alembic upgrade head && uvicorn ocean_read.main:app --host 0.0.0.0 --port 8000"
