# OpenBuild — Development Guide

## Quick Start

```bash
# Start all services (PostgreSQL, Redis, MinIO)
docker compose up -d

# Install frontend dependencies
cd apps/web && npm install

# Run frontend dev server
npm run dev

# Run backend (requires Rust toolchain)
cd apps/api && cargo run

# Run database migrations
cd apps/api && sqlx migrate run
```

## Monorepo Structure

- `apps/web/` — React frontend (Vite + TypeScript)
- `apps/api/` — Rust backend (Axum)
- `packages/ui/` — Shared design system (Tailwind + Radix)
- `packages/pdf-engine/` — PDF annotation/measurement library
- `packages/cost-codes/` — CSI MasterFormat database and utilities
- `packages/types/` — Shared TypeScript types

## Coding Standards

### Commits
Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

### TypeScript (Frontend)
- Strict TypeScript. No `any` types except at API boundaries with explicit casting.
- Zustand for state management. No Redux.
- TanStack Query for server state.
- Tailwind CSS + Radix UI primitives for the design system.
- All components must be accessible (WCAG 2.1 AA).
- PDF viewer must maintain 60fps during pan/zoom on sheets up to 200MB.

### Rust (Backend)
- Use `sqlx` with compile-time query verification.
- Error handling: `thiserror` for library errors, `anyhow` for application.
- All API routes return structured JSON errors with error codes.
- Use `tower` middleware for auth, logging, rate limiting.

### Database
- All tables have `id` (UUID), `created_at`, `updated_at`, `created_by`.
- Soft deletes via `deleted_at`. Hard deletes only via admin.
- Monetary values stored as integers (cents). Never floating point.
- Cost codes follow CSI MasterFormat 2016 structure.
- Row-level security for multi-tenant isolation.

### API Design
- RESTful with OpenAPI 3.1 spec.
- Cursor-based pagination.
- Bulk operations for imports.

## Development Priorities
1. Data integrity — financial documents must never be lost or corrupted
2. Usability — if it's not obvious, it's wrong
3. Performance — large PDFs and datasets are the norm
4. Simplicity — fewer features done well beats many done poorly
5. Extensibility — support phases 2-6 without rewrites

## Testing
```bash
# Frontend tests
cd apps/web && npm test

# Backend tests
cd apps/api && cargo test

# E2E tests
cd apps/web && npm run test:e2e
```
