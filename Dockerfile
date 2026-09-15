# Python-Boilerplate/Dockerfile
FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS base

ENV PYTHONUNBUFFERED=1 POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends build-essential git tk && \
    rm -rf /var/lib/apt/lists/*

ARG APP_VERSION=0.0.0
ARG APP_COMMIT=unknown

ENV APP_VERSION=$APP_VERSION
ENV APP_COMMIT=$APP_COMMIT

COPY pyproject.toml poetry.lock* README.md /app/

RUN pip install --no-cache-dir poetry && \
    poetry install --no-root --only main && \
    poetry run python -c "import psycopg"

COPY src /app/src
COPY typings /app/typings
COPY geo /app/geo
ENV PYTHONPATH=/app/src:/app

FROM base AS test

ENV CI=true

RUN poetry install --no-root --with dev

COPY tests /app/tests

CMD ["poetry", "run", "pytest"]

FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS runtime

ARG APP_VERSION=0.0.0
ARG APP_COMMIT=unknown
ENV PYTHONUNBUFFERED=1 APP_VERSION=$APP_VERSION APP_COMMIT=$APP_COMMIT
ENV PYTHONPATH=/app/src:/app
WORKDIR /app
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends tk \
    && rm -rf /var/lib/apt/lists/*
COPY --from=base /app /app

ENV PATH="/app/.venv/bin:$PATH"
RUN /app/.venv/bin/python -m pip uninstall -y pip setuptools wheel \
    && /usr/local/bin/python -m pip uninstall -y poetry pip setuptools wheel

EXPOSE 8000

CMD ["python", "-m", "app.main_sync"]
