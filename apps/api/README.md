# OpenBuild API

Rust (Axum) backend. See the repo-root `CLAUDE.md` for coding standards and
`docs/api-reference.md` for endpoint documentation.

## Running

```bash
docker compose up -d          # PostgreSQL, Redis, MinIO
cargo run                     # runs migrations on startup, listens on :3000
```

Environment: see `.env.example` at the repo root. `DATABASE_URL` defaults to
the docker-compose Postgres.

## Multi-tenant isolation

All route queries are scoped to the caller's organization. Until JWT
middleware lands, an auth-context stub (`services::auth::SYSTEM_ORG_ID` /
`SYSTEM_USER_ID`) pins every request to the seeded System organization
(migration 003), and the connection pool sets `app.current_org_id` on
connect, which the row-level-security policies (migration 004) key on.

Note: RLS applies to table owners (`FORCE ROW LEVEL SECURITY`) but not to
superusers. The docker-compose dev database creates `openbuild` as a
superuser, so in dev the org-scoped queries are the active isolation layer;
production deployments should connect as a dedicated non-superuser role.

## Known deviation: runtime SQL instead of sqlx macros

CLAUDE.md calls for `sqlx` compile-time query verification (`query!` /
`query_as!`). The API currently uses runtime `sqlx::query` /
`sqlx::query_as` strings instead. This is a deliberate, temporary deviation:

- The macros need a `DATABASE_URL` at compile time or committed `.sqlx`
  offline metadata (generated with `cargo sqlx prepare`), which changes the
  contributor build workflow.
- Most queries return rows with custom Postgres enums (`measurement_type`,
  `project_status`, …) and JSONB columns, which the macros cannot infer
  through `SELECT *` — each query needs an explicit column list with
  per-column type overrides.

Migrating is tracked work: introduce `cargo sqlx prepare` + a committed
`.sqlx` directory in CI, then convert queries module by module. Until then,
schema drift is caught by the migrations running at startup and by
integration tests, not at compile time.
