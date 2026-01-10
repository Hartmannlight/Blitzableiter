# Blitzableiter

Blitzableiter monitors speed traps and traffic hazards and sends notifications when they appear in
your selected areas. You define those areas in a GeoJSON file, and alerts are delivered via
Telegram, Discord, or email.

## User installation (Docker only)
1) Copy `config.yml.example` to `config.yml` and add at least one GeoJSON file (see Configuration below).
2) Create a `.env` file with your sender secrets, for example:
```
BLITZ_DISCORD_URL=https://discord.com/api/webhooks/...
```
3) Create a `docker-compose.yml` (replace `<org-or-user>` and `<repo>`):
```yaml
version: '3.9'

services:
  app:
    image: ghcr.io/<org-or-user>/<repo>:latest
    env_file:
      - .env
    environment:
      APP_SERVICE_NAME: blitzableiter
      APP_ENV: prod
      APP_LOG_LEVEL: INFO
      APP_HEALTH_FILE: /tmp/app-health.json
      APP_CONFIG_PATH: /app/config.yml
      BLITZ_DATABASE_URL: postgresql://blitz:blitz@db:5432/blitz
    volumes:
      - ./config.yml:/app/config.yml:ro
      - ./geo:/data/geo:ro
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: blitz
      POSTGRES_USER: blitz
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-blitz}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```
4) Start the stack:
```
docker compose up -d
```
5) Health check:
```
docker compose exec app poetry run app-health
```

## Configuration
Config precedence is env vars > YAML (`config.yml`) > defaults. All time-of-day values are UTC.

Example `config.yml`:
```yaml
health_file: .app-health.json

global:
  language: en                # "en" or "de"
  default_interval: 900        # seconds
  peak_interval: 300           # seconds
  peak_hours_utc:
    - "07:00-09:00"
    - "16:00-18:00"
  filters:
    types: ["ts", "0", "1", "2", "3", "4", "5", "6", "vwd"]
  reminder:
    enable: true
    maximum_days: 3
    time_of_day_utc: "08:00"

senders:
  telegram_main:
    kind: telegram
    chat_id: "12345678"
    token_env: "BLITZ_TELEGRAM_TOKEN"

  discord_alerts:
    kind: discord_webhook
    url_env: "BLITZ_DISCORD_URL"

  email_ops:
    kind: email
    from: "alert@example.com"
    to: "ops@example.com"
    smtp_host_env: "BLITZ_SMTP_HOST"
    smtp_user_env: "BLITZ_SMTP_USER"
    smtp_pass_env: "BLITZ_SMTP_PASS"

areas:
  karlsruhe_city:
    geojson_path: "/data/geo/karlsruhe_city.geojson"
    senders:
      - telegram_main
      - discord_alerts
```

YAML fields:
- `health_file`: heartbeat file path used by `app-health` (default `.app-health.json`).
- `global.language`: `en` or `de` (default `en`).
- `global.default_interval`: seconds between polls outside peak windows (default `900`).
- `global.peak_interval`: seconds between polls inside peak windows (default `300`).
- `global.peak_hours_utc`: list of windows like `"07:00-09:00"` (UTC).
- `global.filters.types`: list of POI type codes (default full set).
- `global.reminder.enable`: enable daily reminders (default `true`).
- `global.reminder.maximum_days`: max reminder days per POI (default `3`).
- `global.reminder.time_of_day_utc`: reminder trigger time (UTC).
- `senders.<name>.kind`: `telegram`, `discord_webhook`, or `email`.
- `senders.<name>.token_env`: env var name for Telegram token.
- `senders.<name>.chat_id`: Telegram chat id.
- `senders.<name>.url_env`: env var name or literal Discord webhook URL.
- `senders.<name>.smtp_host_env`, `smtp_user_env`, `smtp_pass_env`: SMTP env var names.
- `senders.<name>.from`, `senders.<name>.to`: email addresses.
- `areas.<name>.geojson_path`: file path to GeoJSON (in container).
- `areas.<name>.senders`: list of sender names.

Environment variables:

| Name | Purpose | Default | Example |
| --- | --- | --- | --- |
| `APP_CONFIG_PATH` | Where the app reads the YAML configuration file from | `config.yml` | `/app/config.yml` |
| `APP_SERVICE_NAME` | Name used in logs and metrics labels for this service | `python-service` | `blitzableiter` |
| `APP_ENV` | Environment label added to logs and build info | `dev` | `prod` |
| `APP_LOG_LEVEL` | Minimum log level to output | `INFO` | `DEBUG` |
| `APP_LOOP_SLEEP_SECONDS` | Manual override for the loop sleep time between cycles | from `global.default_interval` | `300` |
| `APP_HEALTH_FILE` | Path to the heartbeat file checked by `app-health` | `.app-health.json` | `/tmp/app-health.json` |
| `APP_VERSION` | Version string reported in logs and metrics | — | `1.2.3` |
| `APP_COMMIT` | Commit SHA reported in logs and metrics | — | `abcdef1` |
| `APP_INSTANCE` | Instance identifier reported in logs and metrics | hostname | `prod-eu-1` |
| `BLITZ_DATABASE_URL` | Postgres URL to enable persistence (schema auto-created) | — | `postgresql://user:pass@host:5432/db` |
| `DATABASE_URL` | Alternative Postgres URL if `BLITZ_DATABASE_URL` is not set | — | `postgresql://user:pass@host:5432/db` |
| `BLITZ_DEFAULT_INTERVAL` | Override the default polling interval (seconds) | `900` | `600` |
| `BLITZ_PEAK_INTERVAL` | Override the peak polling interval (seconds) | `300` | `120` |
| `BLITZ_PEAK_HOURS_UTC` | Override peak time windows (comma-separated, UTC) | — | `07:00-09:00,16:00-18:00` |
| `BLITZ_REMINDER_ENABLE` | Enable/disable daily reminder messages | `true` | `false` |
| `BLITZ_REMINDER_MAX_DAYS` | Max number of reminder days per POI | `3` | `1` |
| `BLITZ_REMINDER_TIME_UTC` | Reminder time of day in UTC | — | `08:30` |
| `BLITZ_POI_TYPES` | Override which POI types are requested | full set | `ts,1` |
| `BLITZ_LANGUAGE` | Language for notification text | `en` | `de` |
| `BLITZ_DISABLE_NOTIFICATIONS` | Disable sending notifications (dry run) | `0` | `1` |
| `BLITZ_TELEGRAM_TOKEN` | Telegram bot token used by Telegram sender | — | `123:abc` |
| `BLITZ_DISCORD_URL` | Discord webhook URL used by Discord sender | — | `https://discord.com/api/webhooks/...` |
| `BLITZ_SMTP_HOST` | SMTP host used by email sender | — | `smtp.example.com` |
| `BLITZ_SMTP_USER` | SMTP username used by email sender | — | `user@example.com` |
| `BLITZ_SMTP_PASS` | SMTP password used by email sender | — | `secret` |

## Developer setup
1) Install dependencies:
```
poetry install
```
2) Copy `config.yml.example` to `config.yml` and adjust it for your test area.
3) Start Postgres only:
```
docker compose -f docker-compose.db.yml up -d
```
4) Run the service locally:
```
BLITZ_DATABASE_URL=postgresql://blitz:blitz@localhost:5432/blitz poetry run app-sync
```
5) Run tests:
```
poetry run pytest
```

Developer notes:
- Health checks rely on a heartbeat file (`APP_HEALTH_FILE`) updated after each successful loop.
- Tests also run in Docker via `docker build --target test -t blitzableiter-test .` + `docker run --rm blitzableiter-test`.
- Config precedence is env vars > YAML > defaults; `areas` and `senders` must be defined in YAML.

## Badges
[![CI Status](https://img.shields.io/github/actions/workflow/status/<org-or-user>/<repo>/build.yml?label=CI%20Status)](https://github.com/<org-or-user>/<repo>/actions/workflows/build.yml)
[![Docker Ready](https://img.shields.io/badge/docker-ready-0db7ed?logo=docker&logoColor=white)](https://ghcr.io)
[![Test Coverage](https://img.shields.io/badge/coverage-unknown-lightgrey)](https://github.com/<org-or-user>/<repo>)
[![Ruff](https://img.shields.io/badge/ruff-enabled-2c2f35)](https://github.com/astral-sh/ruff)
[![Metrics](https://img.shields.io/badge/metrics-internal-lightgrey)](https://github.com/<org-or-user>/<repo>)
