# Lightweight Observability Baseline (v3)

Scope: small backend services and home projects that must be stable and observable with low complexity.

Goals:

* Logs are machine-readable, consistent, and easy to search.
* Basic metrics are always available and safe for Prometheus.
* Health can be checked by orchestrators and scripts.
* Runs are identifiable, and failures are reproducible.
* Shutdown and crashes are explicit and measurable.

---

## 1) Logging

### 1.1 Output & format (mandatory)

* All logs MUST be single-line JSON.
* All logs MUST be written to stdout.
* Exactly one log record per line. No multi-line output.

### 1.2 Timestamp & level (mandatory)

* `ts` MUST be an ISO 8601 UTC timestamp ending with `Z`, e.g. `"2026-01-10T02:03:04.123Z"`.
* `ts` MUST include at least milliseconds. More precision (microseconds) is allowed.
* `level` MUST be exactly one of: `"debug"`, `"info"`, `"warning"`, `"error"` (case-sensitive).

### 1.3 Required fields (mandatory, always present)

Every log record MUST contain:

* `ts` – ISO 8601 UTC timestamp (see 1.2)
* `level` – log level (see 1.2)
* `service` – canonical service name (stable across deployments)
* `logger` – module / logger name
* `instance` – hostname or container ID
* `env` – `"dev" | "stg" | "prod"`
* `run_id` – UUID for the current process run (generated on startup)
* `msg` – human-readable message

### 1.4 Build & config fields (mandatory for lifecycle + health-relevant logs)

For logs that describe startup/config/health or any critical state change, the record MUST include:

* `version` – semantic version or build version
* `commit` – git commit SHA (short or full)
* `config_source` – where config came from (file/env/remote/etc.)
* `config_hash` – hash of a sanitized config representation (no secrets)

### 1.5 Error fields (mandatory for error logs)

For log records with `level = "error"`:

* `error` MUST be present (short message; default = `msg`)
* If an exception is attached, logs MUST include:

  * `exception_type` – exception class name
  * `stack` OR `stack_lines`, encoded so the log remains single-line JSON:

    * `stack` MUST NOT contain literal newline characters (it may contain `\n` escapes)
    * `stack_lines` MUST be an array of strings

### 1.6 Event naming (recommended)

* If the log represents a well-known state transition, include:

  * `event` – stable event name
* `event` SHOULD be `snake_case`.

### 1.7 Correlation (optional)

* HTTP services SHOULD propagate a `request_id`.
* If present, `request_id` MUST be included in all logs emitted within that request scope.

### 1.8 Secret safety (mandatory)

* Logs MUST NOT contain secrets (passwords, tokens, private keys).
* If a value might contain secrets, it MUST be redacted before logging.

---

## 2) Lifecycle logging (mandatory events)

All lifecycle logs MUST still contain the required fields from section 1.3.

### 2.1 Startup

#### Startup begin (recommended)

```json
{
  "ts": "2026-01-10T02:03:04.123Z",
  "level": "info",
  "service": "example-service",
  "logger": "app.lifecycle",
  "instance": "container-abc123",
  "env": "prod",
  "run_id": "5f3b2df7-98d0-4ef6-9c6a-0b8c2d9b7b5a",
  "event": "startup_begin",
  "msg": "Service startup began",
  "version": "1.4.2",
  "commit": "a1b2c3d",
  "config_source": "env+file",
  "config_hash": "sha256:..."
}
```

#### Startup success (mandatory)

```json
{
  "ts": "2026-01-10T02:03:06.000Z",
  "level": "info",
  "service": "example-service",
  "logger": "app.lifecycle",
  "instance": "container-abc123",
  "env": "prod",
  "run_id": "5f3b2df7-98d0-4ef6-9c6a-0b8c2d9b7b5a",
  "event": "startup_success",
  "msg": "Service startup succeeded",
  "version": "1.4.2",
  "commit": "a1b2c3d",
  "config_source": "env+file",
  "config_hash": "sha256:..."
}
```

### 2.2 Shutdown (mandatory)

On `SIGINT` or `SIGTERM`, the service MUST emit:

#### Shutdown begin (mandatory)

```json
{
  "ts": "2026-01-10T02:10:00.000Z",
  "level": "info",
  "service": "example-service",
  "logger": "app.lifecycle",
  "instance": "container-abc123",
  "env": "prod",
  "run_id": "5f3b2df7-98d0-4ef6-9c6a-0b8c2d9b7b5a",
  "event": "shutting_down",
  "reason": "SIGTERM",
  "msg": "Shutting down"
}
```

#### Shutdown complete (recommended)

```json
{
  "ts": "2026-01-10T02:10:01.234Z",
  "level": "info",
  "service": "example-service",
  "logger": "app.lifecycle",
  "instance": "container-abc123",
  "env": "prod",
  "run_id": "5f3b2df7-98d0-4ef6-9c6a-0b8c2d9b7b5a",
  "event": "shutdown_complete",
  "msg": "Shutdown complete",
  "shutdown_duration_ms": 1234
}
```

### 2.3 Crash / fatal exit (mandatory)

If the process exits due to an unhandled exception, emit:

```json
{
  "ts": "2026-01-10T02:11:00.000Z",
  "level": "error",
  "service": "example-service",
  "logger": "app.lifecycle",
  "instance": "container-abc123",
  "env": "prod",
  "run_id": "5f3b2df7-98d0-4ef6-9c6a-0b8c2d9b7b5a",
  "event": "crashed",
  "msg": "Application crashed",
  "error": "Application crashed",
  "exception_type": "ValueError",
  "stack": "Traceback (most recent call last):\\n..."
}
```

---

## 3) Metrics

### 3.1 Metrics endpoint (conditional)

* If `metrics_enabled = true`, the service MUST expose `/metrics` on the configured port.

### 3.2 Baseline metrics (mandatory)

The boilerplate MUST include:

* `app_up` (Gauge)

  * `1` while running, `0` once shutdown begins
* `app_build_info` (Gauge with labels `version`, `commit`, `env`, `service`)

  * constant `1`
* `app_iterations_total` (Counter)

  * increments once per iteration (see definition below)
* `app_last_iteration_timestamp_seconds` (Gauge)

  * unix timestamp when the last iteration finished (success or failure)
* `app_iteration_failures_total` (Counter)

  * increments once per failed iteration

Process metrics from the Prometheus client library MAY remain enabled.

### 3.3 Iteration definition (mandatory if you expose iteration metrics)

* An "iteration" MUST be defined as one full cycle of the main loop OR one scheduled job run.
* The service MUST be consistent: one unit of work equals one increment of `app_iterations_total`.
* `app_last_iteration_timestamp_seconds` MUST be set when the iteration finishes.

### 3.4 Optional metrics (recommended)

* `app_iteration_duration_seconds` (Histogram or Summary)

  * duration per iteration
* `app_iteration_failure_reasons_total` (Counter with label `reason`)

  * `reason` MUST be chosen from a fixed, low-cardinality enum (never exception messages)

### 3.5 Optional HTTP metrics (recommended for HTTP services)

If a service exposes an HTTP API, it is RECOMMENDED to add:

* `app_requests_total` (Counter, labels: `route`, `method`, `status`)
* `app_request_duration_seconds` (Histogram, labels: `route`, `method`)
* `app_errors_total` (Counter, labels: `reason`)

Cardinality rules (mandatory if you implement HTTP metrics):

* `route` MUST be the templated route (e.g. `"/users/{id}"`), never the raw path (e.g. `"/users/123"`).
* `reason` MUST be low-cardinality.

---

## 4) Health

### 4.1 CLI health check (mandatory)

Each service MUST expose a CLI health command that:

* exits with `0` on success, `1` on failure
* outputs single-line JSON to stdout

The output MUST include:

* `status` – `"ok" | "fail"`
* `service`
* `env`
* `version`
* `commit`
* `run_id`
* `config_hash`
* `timestamp` – ISO 8601 UTC ending with `Z`
* `checks` – array of check results

Each check entry MUST include:

* `name` – stable check name (e.g. `db`, `redis`, `mqtt`)
* `status` – `"ok" | "fail"`
* `latency_ms` – integer duration

Example:

```json
{
  "status": "ok",
  "service": "example-service",
  "env": "prod",
  "version": "1.4.2",
  "commit": "a1b2c3d",
  "run_id": "5f3b2df7-98d0-4ef6-9c6a-0b8c2d9b7b5a",
  "config_hash": "sha256:...",
  "timestamp": "2026-01-10T02:12:00.000Z",
  "checks": [
    {"name": "self", "status": "ok", "latency_ms": 1},
    {"name": "db", "status": "ok", "latency_ms": 12}
  ]
}
```

Docker healthchecks SHOULD call this CLI.

### 4.2 Optional HTTP health endpoints (recommended for HTTP services)

* `/healthz` – liveness (`200` if process alive)
* `/readyz` – readiness (`200` if dependencies OK, else `503`)

---

## 5) Shutdown behavior

On `SIGINT` or `SIGTERM`:

1. A `shutting_down` lifecycle log MUST be emitted.
2. The main loop MUST stop accepting new work and complete in-flight work (best effort).
3. `app_up` MUST be set to `0` when shutdown begins.
4. The process MUST exit with:

   * `0` after a clean shutdown
   * non-zero after an unhandled exception / crash

Recommended:

* Emit `shutdown_complete` with `shutdown_duration_ms`.

---

## 6) Config hashing (definition)

* `config_hash` MUST be computed from a canonical, deterministic representation of configuration.
* Secrets MUST be excluded or redacted before hashing.
* The hashing algorithm SHOULD be `sha256` and the value formatted like: `"sha256:<hex>"`.
