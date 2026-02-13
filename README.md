# Flask App

## Frontend style notes

The TI-83 retro board theme now lives in:

- `frontend/src/styles/GameBoard.css`
- `frontend/src/styles/App.css`
- `frontend/src/styles/index.css`

### Theme constraints

- Flat monochrome palette with 1px borders only (no gradients, rounded corners, or drop shadows).
- Tile size defaults to `16px` with mobile fallback (`14px`) to preserve level fit.
- Hero/block/door use 8x8 pixel-map silhouettes rendered through CSS `box-shadow` pixels for deterministic alignment.

### Local visual verification

Run a static preview with multiple board layouts:

```bash
python3 -m http.server 4173
```

Then open:

- `http://127.0.0.1:4173/frontend/preview/index.html`

Use this page to validate sprite positioning, block alignment, and responsive scaling before merging style updates.

### Guardrail check (pre-commit / CI)

Run the retro-style guard script to prevent regressions (gradients, rounded corners, non-board shadows, and tile-size drift):

```bash
./scripts/check_retro_css.sh
```

Install a local git pre-commit hook so the check runs automatically:

```bash
./scripts/install_git_hook.sh
```

Hook installer behavior:
- Creates `.git/hooks/pre-commit` if missing.
- Appends a marked retro-check block if an existing hook is already present (non-destructive).
- Does not duplicate the retro-check block when re-run.


Quick commands:

```bash
make retro-check
make install-hooks
make ci-retro
```

### CI enforcement

GitHub Actions runs the same checks on style-related pull requests and pushes to `main`:

- `.github/workflows/retro-css-guardrails.yml`

CI steps:
- Ensures `ripgrep` and `shellcheck` are available.
- Runs `make ci-retro` (bash syntax checks + shellcheck + guardrail checks).


See `CONTRIBUTING.md` for the pre-PR checklist.
