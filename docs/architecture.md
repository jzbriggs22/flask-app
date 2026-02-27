# OpenBuild Architecture

## Overview

OpenBuild is a monorepo-based construction management platform built with:
- **Frontend:** React + TypeScript (Vite)
- **Backend:** Rust (Axum)
- **Database:** PostgreSQL + TimescaleDB
- **File Storage:** S3-compatible (MinIO for self-hosted)

## System Architecture

```
┌─────────────────────────────────────────────────┐
│                  Browser (PWA)                    │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Projects  │  │ Takeoff  │  │  Estimating   │  │
│  │  Module   │  │  Module  │  │    Module      │  │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│       │              │                │           │
│  ┌────┴──────────────┴────────────────┴───────┐  │
│  │           Zustand State + TanStack Query    │  │
│  └─────────────────────┬──────────────────────┘  │
│                        │                          │
│  ┌─────────────────────┴──────────────────────┐  │
│  │         PDF.js + Measurement Engine         │  │
│  │            (WASM for performance)           │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────┬────────────────────────────┘
                       │ REST API
┌──────────────────────┴────────────────────────────┐
│                 Axum API Server                     │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐    │
│  │   Auth   │  │ Projects │  │   Takeoff     │    │
│  │  Routes  │  │  Routes  │  │    Routes     │    │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘    │
│       │              │                │             │
│  ┌────┴──────────────┴────────────────┴───────┐    │
│  │              Service Layer                  │    │
│  └────┬──────────────┬────────────────┬───────┘    │
│       │              │                │             │
│  ┌────┴─────┐  ┌─────┴─────┐  ┌──────┴──────┐    │
│  │PostgreSQL│  │   MinIO   │  │   Redis     │    │
│  │  (SQLx)  │  │  (Files)  │  │  (Cache)    │    │
│  └──────────┘  └───────────┘  └─────────────┘    │
└────────────────────────────────────────────────────┘
```

## Data Flow: Takeoff → Estimate

The core value proposition is the unified flow from measuring quantities on drawings to generating cost estimates:

1. **Upload Drawing Set** → PDF stored in MinIO, pages extracted, thumbnails generated
2. **Create Takeoff Layers** → Organize by trade (Concrete, Steel, Electrical, etc.)
3. **Calibrate Scale** → Set real-world scale from a known dimension on the drawing
4. **Measure Quantities** → Draw polylines (linear), polygons (area), or click (count)
5. **Assign Cost Codes** → CSI MasterFormat codes linked to each measurement
6. **Generate Estimate** → Measurements flow into estimate line items with unit costs
7. **Export** → Excel/PDF bid package for submission

## Key Design Decisions

### Integer Arithmetic for Money
All monetary values are stored as `BIGINT` cents (or mills for sub-cent precision). This prevents floating-point rounding errors that compound across thousands of line items.

### Soft Deletes
Construction documents have legal significance. Nothing is permanently deleted — all entities use `deleted_at` timestamps for audit trail compliance.

### UUID Primary Keys
Enable offline-first support (Phase 5) and multi-region deployments without coordination.

### JSONB for Measurement Geometry
Measurement points are stored as JSONB arrays. This allows flexible geometry (polylines, polygons, rectangles) without schema changes.
