# OpenBuild

**Open-source, end-to-end construction management platform.**

OpenBuild eliminates the fragmentation plaguing the construction industry by providing a unified platform where data flows seamlessly between estimating, budgeting, project management, scheduling, and field operations.

## MVP — Unified Takeoff & Estimating

The first release focuses on replacing the broken takeoff-to-costing workflow. Instead of measuring quantities in one tool (OST, Bluebeam) and exporting to another (Excel, QuickBid), OpenBuild unifies this into a single flow.

### Features

- **PDF Viewer** — Upload, view, and navigate multi-sheet construction drawing sets
- **Scale Calibration** — Set drawing scale from known dimensions
- **Measurement Tools** — Linear (pipes, walls), area (flooring, painting), count (fixtures, outlets)
- **Takeoff Layers** — Organize measurements by trade/scope with color coding
- **Cost Code Assignment** — CSI MasterFormat codes for every measurement
- **Unit Cost Entry** — Manual unit costs per line item
- **Estimate Summary** — Tabular view with subtotals by division, exportable to Excel/PDF
- **Drawing Revision Comparison** — Overlay two revisions to highlight changes
- **Multi-user Access** — Role-based access (admin, estimator, viewer)
- **Project Organization** — Create projects, upload drawing sets, manage estimates

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Node.js](https://nodejs.org/) 20+
- [Rust](https://rustup.rs/) 1.75+

### Development

```bash
# Start infrastructure services
docker compose up -d

# Install frontend dependencies and start dev server
cd apps/web
npm install
npm run dev

# In another terminal, start the backend
cd apps/api
cargo run
```

The frontend runs at `http://localhost:5173` and the API at `http://localhost:3000`.

### Self-Hosted Deployment

```bash
docker compose -f docker-compose.prod.yml up -d
```

## Architecture

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript (Vite) |
| PDF Engine | PDF.js + custom annotation layer |
| Backend API | Rust (Axum) |
| Database | PostgreSQL + TimescaleDB |
| Search | Meilisearch |
| File Storage | S3-compatible (MinIO) |
| Cache | Redis |

## Project Structure

```
openbuild/
├── apps/
│   ├── web/          # React frontend
│   └── api/          # Rust backend
├── packages/
│   ├── ui/           # Shared design system
│   ├── pdf-engine/   # PDF annotation/measurement library
│   ├── cost-codes/   # CSI MasterFormat database
│   └── types/        # Shared TypeScript types
├── migrations/       # PostgreSQL migrations
├── seeds/            # Sample data
├── docs/             # Documentation
└── deploy/           # Deployment configs
```

## License

[AGPLv3](LICENSE) — Open-core model. The platform is fully open-source.
