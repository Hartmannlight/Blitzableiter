# Python Boilerplate – Sync & Async Service Template

This boilerplate provides a clean, minimal, and observable foundation for Python services.
It supports **two execution models**:

1. **Synchronous services** – ideal for cron-style workers, polling loops, data processors, database/HTTP jobs.
2. **Asynchronous services** – ideal for high-concurrency or event-driven systems such as Discord bots, WebSocket clients, async HTTP services, etc.

Both models share the same configuration system, logging baseline, metrics, health checks, Docker setup, and CI pipeline.

---

# 1. Features

### Observability
- Unified **JSON logging** (single line, includes timestamp, instance, env, service, error fields, etc.).
- **Prometheus metrics** endpoint (`/metrics`) with baseline metrics:
  - `app_up`
  - `app_iterations_total`
  - `app_last_iteration_timestamp_seconds`
  - `app_build_info`
- Built-in **health check** (`app-health`) that validates metrics freshness.
- Lifecycle logging for startup, shutdown, and crashes.

### Config
- Load config from:
  - environment variables
  - optional YAML file (`config.yml`)
- Config precedence: **env > YAML > defaults**
- All values are validated and normalized (bool, int, float).

### Sync & Async Runtime Models
- **Sync service**: classic blocking loop (`service_sync.Service`)
- **Async service**: asyncio-based loop (`service_async.AsyncService`)
- Both controlled through separate entry points.

### Development & CI
- Poetry environment
- Pre-commit (mypy, ruff, YAML/TOML/JSON checks)
- GitHub Actions: lint + test + docker build + smoke test
- Dockerfile with build cache support
- Image name for GHCR is derived automatically from the repository name and lowercased in the CI workflow.

---

# 2. When to use Sync vs. Async?

### Use **sync** when:
- You have a simple worker loop ("do something every X seconds").
- You use blocking libraries (e.g. `requests`, psycopg2) and don’t need high concurrency.
- You want minimal complexity.

### Use **async** when:
- You build a Discord bot, FastAPI app, WebSocket client, proxy, or any event-driven system.
- You need to run many I/O operations concurrently.
- You already rely on async libraries (`aiohttp`, `httpx.AsyncClient`, `asyncpg`, etc.).

The boilerplate lets you choose the right model per project without changing the infrastructure.

---

# 3. Directory Structure

```text
src/app
│
├── config.py          # unified configuration loading
├── logging_setup.py   # JSON logging baseline
├── metrics.py         # Prometheus metrics
├── health.py          # CLI health endpoint
│
├── service_sync.py    # synchronous service loop
├── service_async.py   # asynchronous service loop
│
├── main_sync.py       # entry point for sync workers
└── main_async.py      # entry point for async workers
````

---

# 4. Running a Synchronous Service

Sync entry point is installed as:

```bash
poetry run app-sync
```

or via Docker Compose:

```yaml
services:
  app:
    command: ["poetry", "run", "app-sync"]
```

The sync service uses a classic blocking loop:

```python
from app.service_sync import Service

service = Service(config)
service.start()
```

---

# 5. Running an Asynchronous Service

Async entry point is:

```bash
poetry run app-async
```

or via Docker Compose:

```yaml
services:
  app:
    command: ["poetry", "run", "app-async"]
```

The async service runs on asyncio:

```python
from app.service_async import AsyncService

service = AsyncService(config)
await service.start()
```

### Typical use cases:

* Discord bots
* Async HTTP workers
* Websocket clients
* High-concurrency I/O tasks

---

# 6. Health Check

Every container can be validated via:

```bash
poetry run app-health
```

Exit codes:

* `0` → healthy
* `1` → unhealthy

This is the recommended Docker healthcheck command.

Example Docker Compose:

```yaml
healthcheck:
  test: ["CMD", "poetry", "run", "app-health"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s
```

---

# 7. Metrics

If enabled (`metrics_enabled=true`), the service exposes:

```text
http://localhost:<metrics_port>/metrics
```

Baseline metrics provide:

* service liveness (`app_up`)
* total loop iterations (`app_iterations_total`)
* timestamp of last successful iteration (`app_last_iteration_timestamp_seconds`)
* build information (`app_build_info{version,commit,env}`)

These can be scraped by Prometheus and visualized in Grafana.

---

# 8. Logging

All logs follow the unified JSON format:

```json
{
  "ts": "2025-11-22T20:01:23.123456Z",
  "level": "info",
  "service": "python-service",
  "logger": "app.main_sync",
  "instance": "myhost",
  "env": "dev",
  "msg": "Service startup succeeded",
  "event": "startup_success"
}
```

* All logs are single-line JSON on stdout.
* Errors automatically include stack traces (`stack`) and `exception_type`.
* Lifecycle events are logged explicitly: `startup_success`, `shutting_down`, `crashed`.

This makes ingestion into Loki, Elastic, or any JSON-aware log pipeline straightforward.

---

# 9. Configuration

Configuration can come from:

1. Environment variables
2. YAML file (`config.yml`)
3. Defaults

### Example `.env` (see `.env.example`)

```env
# Core service configuration
APP_SERVICE_NAME=python-service
APP_ENV=dev
APP_LOG_LEVEL=INFO

# Build / version metadata (typically injected during CI build)
APP_VERSION=0.1.0
APP_COMMIT=local-dev

# Optional: override instance ID
APP_INSTANCE=local-dev

# Optional: YAML config path (relative to working directory)
APP_CONFIG_PATH=config.yml

# Metrics configuration
APP_METRICS_ENABLED=1
APP_METRICS_PORT=8000

# Main loop configuration
APP_LOOP_SLEEP_SECONDS=5.0
```

### Example `config.yml` (see `config.yml.example`)

```yaml
service_name: python-service
env: dev
log_level: INFO

metrics_enabled: true
metrics_port: 8000

loop_sleep_seconds: 5.0

version: 0.1.0
commit: local-dev
```

Environment variables override YAML values; YAML overrides hardcoded defaults.

---

# 10. Tests

Run the full test suite:

```bash
poetry run pytest
```

Coverage is configured via `coverage.ini` / `[tool.coverage.*]` in `pyproject.toml`.
Pre-commit hooks ensure:

* type checking (mypy)
* linting/formatting (ruff)
* basic file hygiene (YAML/TOML/JSON + whitespace checks)
* an optional GUI-based repo state check before committing.

---

# 11. Docker

Build and run locally:

```bash
docker build -t python-service .
docker run --rm -p 8000:8000 python-service
```

The GitHub Actions workflow:

* installs dependencies
* runs tests
* builds the Docker image
* pushes to GHCR
* performs a smoke test via `/metrics`

The image name is derived from the repository owner and name in CI, lowercased:

* `ghcr.io/<owner>/<repo>` → e.g. `ghcr.io/hartmannlight/python-boilerplate`

You can adjust the image name logic in `.github/workflows/build.yml` if needed.

---

# 12. Summary

This boilerplate lets you start any kind of Python backend quickly:

* **Sync workers** for polling, simple loops, and data processing
* **Async services** for event-driven, high-concurrency environments

Everything else (logging, health, metrics, config, CI, Docker) is unified and ready to use.

---

# 13. Checklist: What you should change when using this boilerplate

When you create a new project from this boilerplate, you should review and adapt at least the following items.

### 13.1 Project metadata

* In `pyproject.toml`:

  * `[tool.poetry].name` → your project/package name
  * `[tool.poetry].description` → short description of your service
  * `[tool.poetry].authors` → your name/email
  * `[tool.poetry].version` → initial version (e.g. `0.1.0` for your project)

### 13.2 README and docs

* Update the title and description in `README.md` to match your service.
* If you keep `docs/observability-baseline.md`, you can:

  * either reference it from the README
  * or adapt it to your organization’s standards.

### 13.3 Service entry point

Decide which runtime model you actually need:

* Sync:

  * Use `app-sync` as the main entry point (`poetry run app-sync`).
  * In Docker/Docker Compose, use `["poetry", "run", "app-sync"]`.
* Async:

  * Use `app-async` (`poetry run app-async`).
  * In Docker/Docker Compose, use `["poetry", "run", "app-async"]`.

Optional cleanups:

* If your project will **never** use async, you can remove `service_async.py` and `main_async.py` and the `app-async` script.
* If your project will **only** be async, you can remove `service_sync.py` and `main_sync.py` and the `app-sync` script.

### 13.4 Configuration defaults

Check and adapt:

* `.env.example`

  * `APP_SERVICE_NAME` → canonical name of your service
  * `APP_ENV` → default environment (`dev`, `stg`, `prod`, etc.)
  * `APP_METRICS_PORT` → port that fits your stack
  * `APP_LOOP_SLEEP_SECONDS` → reasonable default for your loop
* `config.yml.example`

  * `service_name`, `env`, `log_level` as appropriate
  * `metrics_enabled`, `metrics_port`
  * `loop_sleep_seconds`
  * `version` / `commit` (cosmetic; usually overwritten by CI)

### 13.5 Docker & CI

* `.github/workflows/build.yml`:

  * The image name is derived automatically from GitHub repository owner and name, lowercased.
  * If you want to push to a different registry or org (e.g. Docker Hub), adjust the `Prepare image name` step.

* `docker-compose.yml` / `docker-compose.override.yml`:

  * Ensure `image:` and `command:` match your desired entry point and registry.
  * Update `container_name:` if you care about the container name.

### 13.6 License

* The template assumes `Apache-2.0` (see workflow labels and usually a `LICENSE` file).
* If you use a different license:

  * Update or replace `LICENSE`.
  * Adjust the `org.opencontainers.image.licenses` label in `.github/workflows/build.yml` if needed.

### 13.7 Repo-state check script (optional)

* `scripts/repo_state_check_gui.py`:

  * This is optional tooling to show a small GUI before committing.
  * You can:

    * Adapt the checks (e.g. enforce email domain, branch naming),
    * Or remove this hook from `.pre-commit-config.yaml` if you don’t want interactive confirmation dialogs.

### 13.8 Observability integration

* Ensure your logging/metrics/health expectations match:

  * If you add HTTP endpoints, consider:

    * `/healthz` and `/readyz`
    * HTTP metrics (`app_requests_total`, etc.)
* If you use Prometheus/Grafana:

  * Wire the metrics endpoint into your scrape config.
  * Optionally add dashboards around `app_up`, `app_iterations_total`, and `app_build_info`.

Once you have gone through this checklist and adapted these points, the boilerplate should behave as a first-class, project-specific service template in your environment.
