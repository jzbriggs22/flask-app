-- OpenBuild Initial Schema
-- All tables have: id (UUID), created_at, updated_at, created_by
-- Monetary values in cents (integer). Soft deletes via deleted_at.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Custom enum types
CREATE TYPE user_role AS ENUM ('admin', 'pm', 'estimator', 'super', 'sub', 'owner', 'architect');
CREATE TYPE project_status AS ENUM ('active', 'archived', 'bid', 'closed');
CREATE TYPE measurement_type AS ENUM ('linear', 'area', 'count', 'volume');
CREATE TYPE estimate_status AS ENUM ('draft', 'submitted', 'approved');

-- ============================================================
-- Organizations
-- ============================================================
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Users
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'estimator',
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_org ON users(organization_id);

-- ============================================================
-- Projects
-- ============================================================
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    number TEXT NOT NULL DEFAULT '',
    status project_status NOT NULL DEFAULT 'active',
    address TEXT,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_projects_org ON projects(organization_id);
CREATE INDEX idx_projects_status ON projects(status) WHERE deleted_at IS NULL;

-- ============================================================
-- Drawing Sets
-- ============================================================
CREATE TABLE drawing_sets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    file_url TEXT NOT NULL DEFAULT '',
    file_size BIGINT NOT NULL DEFAULT 0,
    sheet_count INTEGER NOT NULL DEFAULT 0,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drawing_sets_project ON drawing_sets(project_id);

-- ============================================================
-- Drawing Sheets (individual pages within a drawing set)
-- ============================================================
CREATE TABLE drawing_sheets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drawing_set_id UUID NOT NULL REFERENCES drawing_sets(id) ON DELETE CASCADE,
    sheet_number TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    page_index INTEGER NOT NULL,
    thumbnail_url TEXT
);

CREATE INDEX idx_drawing_sheets_set ON drawing_sheets(drawing_set_id);

-- ============================================================
-- Takeoff Layers
-- ============================================================
CREATE TABLE takeoff_layers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drawing_set_id UUID NOT NULL REFERENCES drawing_sets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#3b82f6',
    cost_code TEXT NOT NULL DEFAULT '',
    visible BOOLEAN NOT NULL DEFAULT true,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_takeoff_layers_set ON takeoff_layers(drawing_set_id);

-- ============================================================
-- Measurements (individual takeoff measurements)
-- ============================================================
CREATE TABLE measurements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    layer_id UUID NOT NULL REFERENCES takeoff_layers(id) ON DELETE CASCADE,
    sheet_id UUID NOT NULL REFERENCES drawing_sheets(id),
    measurement_type measurement_type NOT NULL,
    points JSONB NOT NULL DEFAULT '[]',
    value DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT '',
    cost_code TEXT NOT NULL DEFAULT '',
    label TEXT,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_measurements_layer ON measurements(layer_id);
CREATE INDEX idx_measurements_sheet ON measurements(sheet_id);

-- ============================================================
-- Scale Calibrations (per drawing sheet)
-- ============================================================
CREATE TABLE scale_calibrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sheet_id UUID NOT NULL REFERENCES drawing_sheets(id) ON DELETE CASCADE,
    point1_x DOUBLE PRECISION NOT NULL,
    point1_y DOUBLE PRECISION NOT NULL,
    point2_x DOUBLE PRECISION NOT NULL,
    point2_y DOUBLE PRECISION NOT NULL,
    real_distance DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL DEFAULT 'ft',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scale_calibrations_sheet ON scale_calibrations(sheet_id);

-- ============================================================
-- Estimates
-- ============================================================
CREATE TABLE estimates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    status estimate_status NOT NULL DEFAULT 'draft',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_estimates_project ON estimates(project_id);

-- ============================================================
-- Estimate Line Items
-- ============================================================
CREATE TABLE estimate_line_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estimate_id UUID NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    cost_code TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT '',
    -- Unit cost in cents. NEVER use floating point for money.
    unit_cost_cents BIGINT NOT NULL DEFAULT 0,
    -- Optional link back to the takeoff measurement
    measurement_id UUID REFERENCES measurements(id),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_line_items_estimate ON estimate_line_items(estimate_id);
CREATE INDEX idx_line_items_cost_code ON estimate_line_items(cost_code);

-- ============================================================
-- Updated-at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_drawing_sets_updated_at BEFORE UPDATE ON drawing_sets FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_estimates_updated_at BEFORE UPDATE ON estimates FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_line_items_updated_at BEFORE UPDATE ON estimate_line_items FOR EACH ROW EXECUTE FUNCTION update_updated_at();
