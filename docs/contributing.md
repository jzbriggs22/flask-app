# Contributing to OpenBuild

## Getting Started

1. Fork the repository
2. Clone your fork
3. Start infrastructure: `docker compose up -d`
4. Set up the frontend: `cd apps/web && npm install && npm run dev`
5. Set up the backend: `cd apps/api && cargo run`

## Development Workflow

1. Create a feature branch: `git checkout -b feat/your-feature`
2. Make your changes
3. Run tests: `npm test` (frontend), `cargo test` (backend)
4. Commit using conventional commits: `feat: add measurement export`
5. Push and open a pull request

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `refactor:` — Code restructuring without behavior change
- `test:` — Adding or updating tests
- `chore:` — Build, CI, tooling changes

## Code Review

All PRs require:
- Passing CI (linting, tests, type checking)
- At least one approval
- No unresolved conversations

## Architecture Decisions

For significant changes, open a discussion first. We use lightweight ADRs (Architecture Decision Records) in `docs/decisions/`.
