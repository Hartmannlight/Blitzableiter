# Lightweight Observability Baseline

Scope: small backend services and home projects that should be stable and observable with low complexity.

Goals:
- Logs are machine-readable and consistent.
- Basic metrics are always available.
- Health can be checked by container orchestrators or external scripts.
- Shutdown is predictable and visible.

---

## 1. Logging

### Format

- All logs MUST be single-line JSON.
- All logs MUST be written to stdout.

### Required fields (always present)

Every log record MUST contain:

- `ts` – ISO 8601 UTC timestamp, e.g. `"2025-11-22T20:01:23.123456Z"`
- `level` – `"debug"`, `"info"`, `"warning"`, `"error"`
- `service` – canonical service name
- `logger` – module / logger name
- `instance` – hostname or container ID
- `env` – `"dev"`, `"stg"`, `"prod"`
- `msg` – human-readable message

### Error fields

For log records with `level = "error"`:

- `error` MUST be present (short message, default = `msg`)
- If an exception is attached, logs SHOULD include:
  - `stack` – stack trace
  - `exception_type` – exception class name

### Lifecycle events

The service SHOULD emit explicit lifecycle logs:

#### Startup success
```json
{
  "level": "info",
  "event": "startup_success",
  "msg": "Service startup succeeded",
  "version": "...",
  "commit": "...",
  "config_source": "..."
}
````

#### Shutdown

```json
{
  "level": "info",
  "event": "shutting_down",
  "reason": "SIGTERM",
  "msg": "Shutting down"
}
```

#### Crash

```json
{
  "level": "error",
  "event": "crashed",
  "msg": "Application crashed",
  "error": "Application crashed",
  "stack": "...",
  "exception_type": "..."
}
```

### Request correlation (optional)

Projects with HTTP APIs SHOULD propagate a `request_id`.
Worker/loop services MAY omit this.

---

## 2. Metrics

### Metrics endpoint

* If `metrics_enabled = true`, the service MUST expose `/metrics` on the configured port.

### Baseline metrics

The boilerplate MUST include:

* `app_up` (Gauge)
* `app_iterations_total` (Counter)
* `app_last_iteration_timestamp_seconds` (Gauge)
* `app_build_info` (Gauge with labels `version`, `commit`, `env`)

Process metrics from the Prometheus client library MAY remain enabled.

### Optional HTTP metrics

For services with HTTP APIs, it is RECOMMENDED to add:

* `app_requests_total` (Counter, labels: `route`, `method`, `status`)
* `app_request_duration_seconds` (Histogram, labels: `route`, `method`)
* `app_errors_total` (Counter, labels: `reason`)

These are implemented per project and not part of the minimal boilerplate.

---

## 3. Health

### CLI health check (mandatory)

Each service MUST expose a CLI health command that:

* Exits with `0` on success, `1` on failure
* Outputs JSON:

```json
{
  "status": "ok",
  "service": "...",
  "env": "...",
  "version": "...",
  "commit": "...",
  "timestamp": "..."
}
```

Docker healthchecks SHOULD call this CLI.

### Optional HTTP health endpoints

If a service exposes an HTTP API, it is RECOMMENDED to add:

* `/healthz` – liveness (`200` if process alive)
* `/readyz` – readiness (`200` if dependencies OK, else `503`)

---

## 4. Shutdown

On `SIGINT` or `SIGTERM`:

1. A `shutting_down` event SHOULD be logged.
2. The main loop MUST stop and set `app_up` to `0`.
3. The process SHOULD exit with `0` after clean shutdown.
