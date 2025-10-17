# Task Registry FastAPI Service

A FastAPI-powered service that stores explicit task and user state so agents can rely on structured memory rather than implicit context. Tasks use absolute identifiers, track dependencies, and support bulk updates for workflow automation.

## Features

- FastAPI + SQLAlchemy stack with Pydantic validation and dependency normalisation.
- REST endpoints for user CRUD, task CRUD, filtering, and bulk updates.
- Memory nodes and edges that form a neural-style web backed by absolute identifiers for durable agent recall.
- Environment-driven configuration with `.env` template and SQLite default.
- Built-in API key authentication plus sliding window or Redis-backed rate limiting for enterprise use.
- Optional HMAC request signing, per-key scopes, metadata, and automated expiry with rotation tooling.
- Dedicated `/metrics` endpoint guarded by monitor scope or metrics credential.
- Structured JSON logging ready for SIEM ingestion.
- Vault write-through for new API keys so operators can distribute secrets via HashiCorp Vault.
- Structured audit logging with isolated sink configuration for Cloud/SIEM forwarding.
- Request analytics per API key, including request/error counters and last error tracking.
- Metrics caching with per-status gauges to keep Prometheus scrapes lightweight.
- CORS enabled for local experimentation with external agent clients.
- Pytest coverage for the main task, memory, and user behaviours.

## Quick start

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Available variables:

   | Variable | Default | Description |
   | --- | --- | --- |
   | `DATABASE_URL` | `sqlite:///instance/app.db` | SQLAlchemy database connection URI. |
   | `API_AUTH_ENABLED` | `true` | Require API key authentication on every request. |
   | `API_KEY_HEADER` | `X-API-Key` | Header that must include the plaintext API key. |
   | `API_HMAC_ENABLED` | `false` | Enforce timestamped HMAC signatures using the API key as the shared secret. |
   | `API_SIGNATURE_HEADER` | `X-Signature` | Header carrying the hexadecimal HMAC signature. |
   | `API_TIMESTAMP_HEADER` | `X-Timestamp` | Header containing the UNIX timestamp used in the signature payload. |
   | `API_TIMESTAMP_TOLERANCE_SECONDS` | `300` | Maximum allowed drift (in seconds) for signed requests. |
   | `API_KEY_DEFAULT_TTL_DAYS` | `0` | Default TTL in days for keys (0 disables auto-expiry). |
   | `API_KEY_AUTO_EXPIRY_ENABLED` | `true` | Toggle background pruning of expired API keys. |
   | `API_KEY_EXPIRY_CHECK_SECONDS` | `900` | Interval (seconds) for the expiry background worker. |
   | `RATE_LIMIT_ENABLED` | `true` | Toggle rate limiting dependency. |
   | `RATE_LIMIT_PER_MINUTE` | `180` | Requests per minute allowed per principal and route. |
   | `RATE_LIMIT_BURST` | `60` | Extra burst capacity beyond the steady-state per-minute cap. |
   | `RATE_LIMIT_IDENTIFIER_HEADER` | `X-API-Key` | Optional override for limiter identification header. |
   | `RATE_LIMIT_BACKEND` | `memory` | Rate limiter backend (`memory` or `redis`). |
   | `RATE_LIMIT_REDIS_URL` | _(empty)_ | Redis connection URL when using the Redis limiter backend. |
   | `ALLOWED_ORIGINS` | `["*"]` | JSON list of CORS origins permitted to call the API. |
   | `METRICS_KEY` | _(empty)_ | Shared secret enabling `/metrics` access without monitor scope. |
   | `METRICS_KEY_HEADER` | `X-Metrics-Key` | Header that must carry the metrics credential. |
   | `METRICS_CACHE_SECONDS` | `15` | TTL for cached `/metrics` responses (`0` disables caching). |
   | `VAULT_ENABLED` | `false` | Persist new API keys to HashiCorp Vault when true. |
   | `VAULT_ADDR` | `http://127.0.0.1:8200` | Vault server address. |
   | `VAULT_TOKEN` | _(empty)_ | Vault token used for write access. |
   | `VAULT_NAMESPACE` | _(empty)_ | Optional Vault namespace header. |
   | `VAULT_MOUNT_POINT` | `secret` | KV v2 mount used for API key storage. |
   | `VAULT_PATH_PREFIX` | `task-registry/api-keys` | Prefix for secrets written to Vault. |
   | `VAULT_VERIFY_SSL` | `true` | Toggle TLS verification when talking to Vault. |
   | `AUDIT_LOG_ENABLED` | `true` | Enable structured audit logging. |
   | `AUDIT_LOG_DESTINATION` | `stdout` | Audit sink (`stdout`, `file`, or `http`). |
   | `AUDIT_LOG_FILE_PATH` | _(empty)_ | File path when using file-based audit logging. |
   | `AUDIT_LOG_HTTP_ENDPOINT` | _(empty)_ | HTTP endpoint for forwarding audit events (e.g., Splunk HEC). |

3. **Provision an API key**

   ```bash
   python -m app.cli create-api-key service-bot
   ```

   Store the returned secret securely and send it in the `X-API-Key` header for every request.

4. **Run the API**

   ```bash
   uvicorn app.main:app --reload
   ```

   The OpenAPI docs are available at http://127.0.0.1:8000/docs

5. **Execute tests**

   ```bash
   pytest
   ```

## API overview

| Method | Endpoint                | Description                                         |
| ------ | ----------------------- | --------------------------------------------------- |
| GET    | `/healthz`              | Health probe                                        |
| POST   | `/users`                | Create a user                                       |
| GET    | `/users`                | List users                                          |
| GET    | `/users/{id}`           | Retrieve a user                                     |
| POST   | `/tasks`                | Create a task with absolute identifier              |
| GET    | `/tasks`                | List tasks with optional filters                    |
| GET    | `/tasks/{task_id}`      | Retrieve a task                                     |
| PATCH  | `/tasks/{task_id}`      | Update a task                                       |
| DELETE | `/tasks/{task_id}`      | Remove a task                                       |
| POST   | `/tasks/bulk-update`    | Bulk update multiple tasks in one request           |
| POST   | `/memory/nodes`         | Create a durable memory node tied to a task         |
| GET    | `/memory/nodes`         | List memory nodes, optionally filtered by task      |
| GET    | `/memory/nodes/{id}`    | Retrieve a memory node by absolute reference        |
| PATCH  | `/memory/nodes/{id}`    | Update memory node metadata or originating task     |
| DELETE | `/memory/nodes/{id}`    | Remove a memory node                                |
| POST   | `/memory/edges`         | Connect nodes/tasks into a neural-style web         |
| GET    | `/memory/edges`         | List edges with filters on source/target references |
| GET    | `/memory/edges/{id}`    | Retrieve an edge                                    |
| PATCH  | `/memory/edges/{id}`    | Update edge relation, weight, or target references  |
| DELETE | `/memory/edges/{id}`    | Remove an edge                                      |
| POST   | `/memory/traces`        | Persist an immutable memory trace entry             |
| GET    | `/memory/traces`        | List trace entries filtered by task, node, or source|
| GET    | `/memory/traces/{id}`   | Retrieve a specific trace entry                     |
| GET    | `/memory/graph`         | Export a focused subgraph for a node or task        |
| GET    | `/tasks/{task}/timeline`| Retrieve chronological trace history for a task     |
| GET    | `/metrics`              | Prometheus metrics gated by monitor scope or metrics key |

## Operational notes

- Set `DATABASE_URL` to PostgreSQL or MySQL for production; ensure credentials live in secrets managers, not the repo.
- Rotate API keys regularly using the management CLI (`python -m app.cli`) to create, list, deactivate, or `rotate-api-key` secrets without downtime.
- Use the optional HMAC headers when exposing the API over untrusted networks to mitigate replay attacks.
- Review indexing strategy if you expect high-cardinality filters beyond project, status, or owner.
- Memory identifiers are forced to uppercase `[A-Z0-9_.:-]` tokens so that agents can reference graph entities unambiguously across calls.
- Enable Vault integration to push generated secrets directly into your organisation's secrets manager during CLI create/rotate commands.
- Audit events are emitted via the `app.audit` logger; point `AUDIT_LOG_DESTINATION` at a file or HTTP collector (e.g., Splunk HEC) to ship them off-box.
- API keys now track total requests, error counts, and the most recent error reason for quicker incident response.
- Cache `/metrics` responses by default; set `METRICS_CACHE_SECONDS=0` if you prefer uncached scrapes during development.

## CLI quick reference

```bash
python -m app.cli create-api-key prod-bot --owner-email ops@example.com --scopes read write monitor --ttl-days 30
python -m app.cli list-api-keys
python -m app.cli deactivate-api-key prod-bot
python -m app.cli rotate-api-key prod-bot --ttl-days 60
python -m app.cli bulk-set-scopes prod-bot qa-bot --add monitor --remove write
python -m app.cli reassign-api-key-owner prod-bot --owner-email security@example.com
```

## Request signing

When `API_HMAC_ENABLED=true`, sign each request using:

```
signature = HMAC_SHA256(key=api_key, message=f"{timestamp}:{method}:{path}")
```

Send the `X-Timestamp` (UNIX epoch seconds) and `X-Signature` (hex digest) headers alongside the usual `X-API-Key` header. The included [`docs/api-examples.http`](docs/api-examples.http) file shows ready-to-run HTTP examples.

