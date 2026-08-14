-- Seed the system organization and user.
--
-- The API currently runs without an auth layer and stamps created_by /
-- uploaded_by / linked_by with the nil UUID. Those columns are NOT NULL
-- foreign keys to users(id), so without this seed every create endpoint
-- fails with an FK violation. When real auth lands, handlers will take
-- the user from the auth context instead; this row remains as the
-- attribution target for system-initiated actions (imports, migrations).

INSERT INTO organizations (id, name, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'System',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, organization_id, email, name, role, password_hash, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    '00000000-0000-0000-0000-000000000000',
    'system@openbuild.local',
    'System',
    'admin',
    '',  -- no password: this account can never log in
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;
