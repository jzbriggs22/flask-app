-- Audit columns and soft delete (CLAUDE.md database rules).
--
-- "All tables have id (UUID), created_at, updated_at, created_by" and
-- "Soft deletes via deleted_at. Hard deletes only via admin."
--
-- Backfills attribution on existing rows with the System user (migration 003).

-- estimate_line_items: attribution + soft delete.
-- Line items are financial records — deleting one must not destroy it or
-- its estimate_line_item_sources traceability rows.
ALTER TABLE estimate_line_items
    ADD COLUMN created_by UUID REFERENCES users(id),
    ADD COLUMN deleted_at TIMESTAMPTZ;

UPDATE estimate_line_items
SET created_by = '00000000-0000-0000-0000-000000000000'
WHERE created_by IS NULL;

ALTER TABLE estimate_line_items ALTER COLUMN created_by SET NOT NULL;

-- takeoff_layers: attribution + updated_at
ALTER TABLE takeoff_layers
    ADD COLUMN created_by UUID REFERENCES users(id),
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE takeoff_layers
SET created_by = '00000000-0000-0000-0000-000000000000'
WHERE created_by IS NULL;

ALTER TABLE takeoff_layers ALTER COLUMN created_by SET NOT NULL;

CREATE TRIGGER trg_takeoff_layers_updated_at
    BEFORE UPDATE ON takeoff_layers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- drawing_sheets: full audit set
ALTER TABLE drawing_sheets
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN created_by UUID REFERENCES users(id);

UPDATE drawing_sheets
SET created_by = '00000000-0000-0000-0000-000000000000'
WHERE created_by IS NULL;

ALTER TABLE drawing_sheets ALTER COLUMN created_by SET NOT NULL;

CREATE TRIGGER trg_drawing_sheets_updated_at
    BEFORE UPDATE ON drawing_sheets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- measurements: updated_at on the materialized row (version history is in
-- measurement_versions; this tracks when the materialized state last moved)
ALTER TABLE measurements
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TRIGGER trg_measurements_updated_at
    BEFORE UPDATE ON measurements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
