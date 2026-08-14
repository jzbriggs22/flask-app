-- OpenBuild Takeoff Engine Schema (v0.1 — "Trust the Pixels" spec)
--
-- This migration adds:
--   - Drawing sheet revisions (measurements bind to revisions, not sheets)
--   - Enriched calibrations (method, confidence, unit_system, world_distance_pt)
--   - Measurement versioning (append-only versions, no silent edits)
--   - Takeoff event log (append-only audit trail)
--   - Estimate line item sources (many-to-many measurement → line item)
--   - Quantity snapshots on line items

-- ============================================================
-- Drawing Sheet Revisions
-- A revision is a specific version of a sheet within a drawing set.
-- Measurements bind to revisions, NOT to sheets directly.
-- When a new revision is uploaded, old measurements stay on the old revision.
-- ============================================================
CREATE TABLE drawing_sheet_revisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sheet_id UUID NOT NULL REFERENCES drawing_sheets(id) ON DELETE CASCADE,
    drawing_set_id UUID NOT NULL REFERENCES drawing_sets(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL DEFAULT 1,
    file_url TEXT NOT NULL DEFAULT '',
    page_index INTEGER NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uploaded_by UUID NOT NULL REFERENCES users(id),
    -- Metadata extracted from the PDF page
    page_width_pt DOUBLE PRECISION,   -- PDF page width in points (1/72 inch)
    page_height_pt DOUBLE PRECISION,  -- PDF page height in points
    rotation INTEGER NOT NULL DEFAULT 0,  -- 0, 90, 180, 270
    UNIQUE (sheet_id, revision_number)
);

CREATE INDEX idx_sheet_revisions_sheet ON drawing_sheet_revisions(sheet_id);
CREATE INDEX idx_sheet_revisions_set ON drawing_sheet_revisions(drawing_set_id);

-- ============================================================
-- Scale Calibrations (enriched per spec §5)
-- Maps WORLD (PDF_PT) → Real-world units.
-- Bound to a specific sheet revision.
-- ============================================================
ALTER TABLE scale_calibrations
    ADD COLUMN sheet_revision_id UUID REFERENCES drawing_sheet_revisions(id),
    ADD COLUMN unit_system TEXT NOT NULL DEFAULT 'imperial'
        CHECK (unit_system IN ('imperial', 'metric')),
    ADD COLUMN display_unit TEXT NOT NULL DEFAULT 'ft'
        CHECK (display_unit IN ('in', 'ft', 'mm', 'm')),
    ADD COLUMN world_distance_pt DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN scale_factor DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN method TEXT NOT NULL DEFAULT 'two-point'
        CHECK (method IN ('two-point', 'known-scale-text', 'pdf-embedded')),
    ADD COLUMN confidence TEXT NOT NULL DEFAULT 'exact'
        CHECK (confidence IN ('exact', 'estimated'));

-- Backfill: compute world_distance_pt from existing calibration points
UPDATE scale_calibrations SET
    world_distance_pt = sqrt(
        power(point2_x - point1_x, 2) + power(point2_y - point1_y, 2)
    ),
    scale_factor = CASE
        WHEN sqrt(power(point2_x - point1_x, 2) + power(point2_y - point1_y, 2)) > 0
        THEN real_distance / sqrt(power(point2_x - point1_x, 2) + power(point2_y - point1_y, 2))
        ELSE 0
    END;

CREATE INDEX idx_calibrations_revision ON scale_calibrations(sheet_revision_id);

-- ============================================================
-- Measurements — add calibration reference and dual quantities
-- Per spec §6: every measurement has calibration_id (nullable = uncalibrated)
-- quantity_raw = WORLD (PDF_PT) derived, quantity_real = calibrated real units
-- ============================================================
ALTER TABLE measurements
    ADD COLUMN sheet_revision_id UUID REFERENCES drawing_sheet_revisions(id),
    ADD COLUMN calibration_id UUID REFERENCES scale_calibrations(id),
    ADD COLUMN quantity_raw DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN quantity_real DOUBLE PRECISION,
    ADD COLUMN uom TEXT NOT NULL DEFAULT '',
    ADD COLUMN deleted_at TIMESTAMPTZ,
    ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

-- Backfill: copy value to quantity_raw for existing rows
UPDATE measurements SET quantity_raw = value;

CREATE INDEX idx_measurements_revision ON measurements(sheet_revision_id);
CREATE INDEX idx_measurements_calibration ON measurements(calibration_id);
CREATE INDEX idx_measurements_not_deleted ON measurements(layer_id) WHERE deleted_at IS NULL;

-- ============================================================
-- Measurement Versions (append-only, per spec §9)
-- "Edit measurement" creates a new version; prior versions remain immutable.
-- ============================================================
CREATE TABLE measurement_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    measurement_id UUID NOT NULL REFERENCES measurements(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    geometry_world JSONB NOT NULL,         -- points in WORLD (PDF_PT)
    calibration_id UUID REFERENCES scale_calibrations(id),
    quantity_raw DOUBLE PRECISION NOT NULL,
    quantity_real DOUBLE PRECISION,
    uom TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',  -- label, notes, tags, cost_code
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES users(id),
    supersedes_version_id UUID REFERENCES measurement_versions(id),
    UNIQUE (measurement_id, version_number)
);

CREATE INDEX idx_mversions_measurement ON measurement_versions(measurement_id);

-- ============================================================
-- Takeoff Events (append-only audit log, per spec §9)
-- Types: MEASUREMENT_CREATED, MEASUREMENT_UPDATED, MEASUREMENT_DELETED,
--        CALIBRATION_SET, LAYER_CREATED, LAYER_UPDATED, LAYER_DELETED
-- ============================================================
CREATE TYPE takeoff_event_type AS ENUM (
    'MEASUREMENT_CREATED',
    'MEASUREMENT_UPDATED',
    'MEASUREMENT_DELETED',
    'CALIBRATION_SET',
    'CALIBRATION_INVALIDATED',
    'LAYER_CREATED',
    'LAYER_UPDATED',
    'LAYER_DELETED',
    'REVISION_UPLOADED'
);

CREATE TABLE takeoff_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id),
    sheet_revision_id UUID REFERENCES drawing_sheet_revisions(id),
    event_type takeoff_event_type NOT NULL,
    -- References to affected entities
    measurement_id UUID REFERENCES measurements(id),
    measurement_version_id UUID REFERENCES measurement_versions(id),
    calibration_id UUID REFERENCES scale_calibrations(id),
    layer_id UUID REFERENCES takeoff_layers(id),
    -- Minimal diff payload
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES users(id)
);

-- Append-only: no UPDATE or DELETE triggers needed (enforce via app logic)
CREATE INDEX idx_events_project ON takeoff_events(project_id);
CREATE INDEX idx_events_type ON takeoff_events(event_type);
CREATE INDEX idx_events_measurement ON takeoff_events(measurement_id);
CREATE INDEX idx_events_created ON takeoff_events(created_at);

-- ============================================================
-- Estimate Line Item Sources (many-to-many, per spec §11)
-- A line item can be driven by multiple measurements.
-- Each source records a quantity snapshot at the time of pricing.
-- ============================================================
CREATE TABLE estimate_line_item_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    line_item_id UUID NOT NULL REFERENCES estimate_line_items(id) ON DELETE CASCADE,
    measurement_id UUID NOT NULL REFERENCES measurements(id),
    measurement_version_id UUID NOT NULL REFERENCES measurement_versions(id),
    -- Snapshot: the quantity at time of linking (spec §11)
    quantity_snapshot DOUBLE PRECISION NOT NULL,
    uom_snapshot TEXT NOT NULL DEFAULT '',
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    linked_by UUID NOT NULL REFERENCES users(id)
);

CREATE INDEX idx_item_sources_line_item ON estimate_line_item_sources(line_item_id);
CREATE INDEX idx_item_sources_measurement ON estimate_line_item_sources(measurement_id);

-- ============================================================
-- Estimate Line Items — add source_type and snapshot fields
-- Per spec §11: items are either "manual" or "driven"
-- ============================================================
ALTER TABLE estimate_line_items
    ADD COLUMN source_type TEXT NOT NULL DEFAULT 'manual'
        CHECK (source_type IN ('manual', 'driven')),
    ADD COLUMN quantity_snapshot DOUBLE PRECISION,
    ADD COLUMN snapshot_at TIMESTAMPTZ,
    ADD COLUMN is_stale BOOLEAN NOT NULL DEFAULT false;
