# Python-Boilerplate/Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

ARG APP_VERSION=0.0.0
ARG APP_COMMIT=unknown

ENV APP_VERSION=$APP_VERSION
ENV APP_COMMIT=$APP_COMMIT

COPY pyproject.toml poetry.lock* /app/

RUN pip install --no-cache-dir poetry && \
    poetry install --no-root --only main

COPY src /app/src
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["poetry", "run", "app"]
