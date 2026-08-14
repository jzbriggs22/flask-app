-- Row-level security for multi-tenant isolation (CLAUDE.md database rules).
--
-- Policies key on the app.current_org_id session setting. The API sets it
-- per connection (pool after_connect); once real auth lands it moves to a
-- per-request SET LOCAL in middleware. FORCE ROW LEVEL SECURITY makes the
-- policies apply even to the table owner, so a query with the setting
-- missing fails loudly (current_setting errors) instead of silently
-- returning another tenant's rows.
--
-- RLS is applied to the tenant-rooted tables. Child tables (sheets,
-- layers, measurements, line items, …) have no organization_id column and
-- are reachable only through org-scoped joins in the API; extending RLS
-- to them via EXISTS policies is planned once auth lands.

-- Projects: the root of all tenant business data
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;

CREATE POLICY projects_tenant_isolation ON projects
    USING (organization_id = current_setting('app.current_org_id')::uuid)
    WITH CHECK (organization_id = current_setting('app.current_org_id')::uuid);

-- Drawing sets: scoped through their project
ALTER TABLE drawing_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE drawing_sets FORCE ROW LEVEL SECURITY;

CREATE POLICY drawing_sets_tenant_isolation ON drawing_sets
    USING (EXISTS (
        SELECT 1 FROM projects p
        WHERE p.id = drawing_sets.project_id
          AND p.organization_id = current_setting('app.current_org_id')::uuid
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM projects p
        WHERE p.id = drawing_sets.project_id
          AND p.organization_id = current_setting('app.current_org_id')::uuid
    ));

-- Estimates: scoped through their project
ALTER TABLE estimates ENABLE ROW LEVEL SECURITY;
ALTER TABLE estimates FORCE ROW LEVEL SECURITY;

CREATE POLICY estimates_tenant_isolation ON estimates
    USING (EXISTS (
        SELECT 1 FROM projects p
        WHERE p.id = estimates.project_id
          AND p.organization_id = current_setting('app.current_org_id')::uuid
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM projects p
        WHERE p.id = estimates.project_id
          AND p.organization_id = current_setting('app.current_org_id')::uuid
    ));
