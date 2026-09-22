# Blitzableiter

Blitzableiter monitors speed traps and traffic hazards and notifies you when they appear in your
GeoJSON-defined areas. Alerts are sent via Telegram, Discord, or email.

## Quick start (Docker)
1) Copy `config.yml.example` to `config.yml` and add at least one GeoJSON file.
2) Create a `.env` file with sender secrets:
```text
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
4) Start:
```text
docker compose up -d
```
5) Health check:
```text
docker compose exec app python -m app.health
```

## Configuration
Config precedence is env vars > YAML (`config.yml`) > defaults. All time-of-day values are UTC.

Example `config.yml`:
```yaml
health_file: .app-health.json

global:
  language: en
  default_interval: 900
  peak_interval: 300
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
    mention_user_id: "150284955140882433"
    enable_map: true

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

Key fields:
- `global.filters.types`: list of POI type codes (see below).
- `senders.<name>.mention_user_id`: Discord user ID to ping (optional).
- `senders.<name>.enable_map`: include map screenshot in Discord embeds (default `true`).
- `areas.<name>.senders`: list of sender names.

POI type codes (from atudo):
- `0`: Fixed speed trap
- `1`: Mobile speed trap
- `2`: Traffic control
- `3`: Red light camera
- `4`: Average speed check
- `5`/`6`: Speed trap
- `vwd`: Hazard / warning
- `ts`: Atudo `ts` type (kept as-is)

Environment variables (common):

| Name | Purpose | Default |
| --- | --- | --- |
| `APP_CONFIG_PATH` | YAML config path | `config.yml` |
| `APP_ENV` | Environment label in logs | `dev` |
| `APP_LOG_LEVEL` | Minimum log level | `INFO` |
| `APP_HEALTH_FILE` | Heartbeat file for `app-health` | `.app-health.json` |
| `BLITZ_DATABASE_URL` | Postgres URL for persistence | unset |
| `BLITZ_LANGUAGE` | Notification language | `en` |
| `BLITZ_POI_TYPES` | Override POI types | full set |
| `BLITZ_DISABLE_NOTIFICATIONS` | Skip all delivery and delivery records while keeping data collection active | `0` |
| `BLITZ_TELEGRAM_TOKEN` | Telegram token | unset |
| `BLITZ_DISCORD_URL` | Discord webhook URL | unset |
| `BLITZ_SMTP_HOST` | SMTP host | unset |
| `BLITZ_SMTP_USER` | SMTP user | unset |
| `BLITZ_SMTP_PASS` | SMTP password | unset |

## Developer setup
1) Install deps: `poetry install`
2) Start Postgres: `docker compose -f docker-compose.db.yml up -d`
3) Run service: `BLITZ_DATABASE_URL=postgresql://blitz:blitz@localhost:5432/blitz poetry run app-sync`
4) Tests: `poetry run pytest`

## Badges
[![CI Status](https://img.shields.io/github/actions/workflow/status/<org-or-user>/<repo>/build.yml?label=CI%20Status)](https://github.com/<org-or-user>/<repo>/actions/workflows/build.yml)
[![Docker Ready](https://img.shields.io/badge/docker-ready-0db7ed?logo=docker&logoColor=white)](https://ghcr.io)
[![Test Coverage](https://img.shields.io/badge/coverage-unknown-lightgrey)](https://github.com/<org-or-user>/<repo>)
[![Ruff](https://img.shields.io/badge/ruff-enabled-2c2f35)](https://github.com/astral-sh/ruff)
[![Metrics](https://img.shields.io/badge/metrics-internal-lightgrey)](https://github.com/<org-or-user>/<repo>)
