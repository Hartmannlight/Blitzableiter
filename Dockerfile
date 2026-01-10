# Python-Boilerplate/Dockerfile
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential git tk && \
    rm -rf /var/lib/apt/lists/*

ARG APP_VERSION=0.0.0
ARG APP_COMMIT=unknown

ENV APP_VERSION=$APP_VERSION
ENV APP_COMMIT=$APP_COMMIT

COPY pyproject.toml poetry.lock* /app/

RUN pip install --no-cache-dir poetry && \
    poetry install --no-root --only main

COPY src /app/src
COPY typings /app/typings
COPY geo /app/geo
ENV PYTHONPATH=/app/src:/app

FROM base AS test

ENV CI=true

RUN poetry install --no-root --with dev

COPY tests /app/tests

CMD ["poetry", "run", "pytest"]

FROM base AS runtime

EXPOSE 8000

CMD ["poetry", "run", "app-sync"]
