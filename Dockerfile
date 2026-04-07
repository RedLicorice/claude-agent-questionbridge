# Stage 1: build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.5

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true \
 && poetry install --only main --no-root --no-interaction --no-ansi

# Stage 2: runtime image
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY questionbridge/ ./questionbridge/
COPY pyproject.toml ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Settings are supplied via a mounted settings.local.yaml or environment variables.
# Example: docker run -v ./settings.local.yaml:/app/settings.local.yaml ...
ENTRYPOINT ["python", "-c", "from questionbridge import start; start()"]
