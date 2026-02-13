# Contributing

## Retro UI guardrails checklist

Run this before every pull request:

```bash
make retro-check
```

Install local git hooks once per clone:

```bash
make install-hooks
```

## PR quality gate

- Keep TI-83 board visuals flat monochrome only.
- Do not introduce gradients, non-zero rounded corners, or app/global shadows.
- Preserve board sizing constraints (`--tile-size: 16px` default, `14px` mobile fallback).
- Verify `frontend/preview/index.html` alignment in browser before requesting review.


## CI-equivalent check locally

```bash
make ci-retro
```
