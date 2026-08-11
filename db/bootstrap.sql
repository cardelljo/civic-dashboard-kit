-- Shared-instance bootstrap: schemas, roles, grants, search_path, and geo.
--
-- Run ONCE as a superuser, before any dashboard applies its own schema.sql.
-- Idempotent: safe to re-run.
--
--     psql "$SUPERUSER_URL" -f db/bootstrap.sql
--
-- This lives in the toolkit rather than in a dashboard because it is exactly
-- what docs/ARCHITECTURE.md §2 and §4 own -- one instance, one schema per
-- dashboard, plus a shared `geo`. A dashboard's own tables stay in its own repo
-- (901economy's db/schema.sql); this file only creates the containers they go in.
--
-- NO PASSWORDS HERE. This repo is public. The roles are created able to log in
-- but with no password, so they cannot authenticate until you set one. After
-- running this, in the same psql session:
--
--     \password economy_app
--     \password education_app
--     \password justice_app
--     \password geo_loader
--
-- `\password` prompts, hashes client-side, and never puts the secret in the
-- file, your shell history, or the process list -- unlike `-v pw=...`.

\echo '== civic-dashboard-kit shared bootstrap =='

-- ---------------------------------------------------------------------------
-- 1. PostGIS
-- ---------------------------------------------------------------------------
-- Lands in `public`, which stays last in every role's search_path below, so
-- `geometry` and the ST_* functions resolve everywhere without qualification.
-- §3: the instance is provisioned from postgis/postgis:18-3.6-alpine, so this is
-- a no-op enable rather than a build.
CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------
-- 2. Schemas -- one per dashboard, plus the shared geo (§2)
-- ---------------------------------------------------------------------------
-- Creating a namespace is NOT a migration commitment. §1 keeps the store choice
-- per dashboard: 901education is on the NDJSON ledger and 901justice is a
-- deliberate judgment call. Their schemas exist here so that if either ever
-- adopts Postgres it slots in without a second bootstrap -- and, more usefully
-- today, so both can read geo.boundaries at build time without owning any of it.
CREATE SCHEMA IF NOT EXISTS economy;
CREATE SCHEMA IF NOT EXISTS education;
CREATE SCHEMA IF NOT EXISTS justice;
CREATE SCHEMA IF NOT EXISTS geo;

-- ---------------------------------------------------------------------------
-- 3. Roles
-- ---------------------------------------------------------------------------
-- One app role per dashboard, plus geo_loader.
--
-- geo_loader exists because `geo` is shared. If economy_app owned it, the other
-- two dashboards would be reading from a namespace one dashboard controls, and
-- "shared" would be true only by convention. A dedicated writer keeps geo's
-- write access independent of any single dashboard -- which is the whole reason
-- §2 puts boundaries in their own schema instead of economy's.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['economy_app', 'education_app', 'justice_app', 'geo_loader']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            -- LOGIN but no password: cannot authenticate until \password is run.
            EXECUTE format('CREATE ROLE %I LOGIN', r);
            RAISE NOTICE 'created role % (set a password with \password %)', r, r;
        ELSE
            RAISE NOTICE 'role % already exists, left alone', r;
        END IF;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------------
-- 4. Ownership -- each role owns its own schema
-- ---------------------------------------------------------------------------
-- Ownership rather than a pile of grants: the app role then creates its own
-- tables when it runs its schema.sql, and owns them, so no follow-up GRANT is
-- needed for its own data. That is what makes this file's job finish here.
ALTER SCHEMA economy   OWNER TO economy_app;
ALTER SCHEMA education OWNER TO education_app;
ALTER SCHEMA justice   OWNER TO justice_app;
ALTER SCHEMA geo       OWNER TO geo_loader;

-- ---------------------------------------------------------------------------
-- 5. geo is readable by every dashboard, writable by none of them
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA geo TO economy_app, education_app, justice_app;
GRANT SELECT ON ALL TABLES IN SCHEMA geo TO economy_app, education_app, justice_app;

-- Tables geo_loader creates LATER are also readable, without revisiting this
-- file. Without this, adding a second geo table silently leaves the dashboards
-- unable to read it -- a permission error at pipeline time, months from now.
ALTER DEFAULT PRIVILEGES FOR ROLE geo_loader IN SCHEMA geo
    GRANT SELECT ON TABLES TO economy_app, education_app, justice_app;
ALTER DEFAULT PRIVILEGES FOR ROLE geo_loader IN SCHEMA geo
    GRANT SELECT, USAGE ON SEQUENCES TO economy_app, education_app, justice_app;

-- ---------------------------------------------------------------------------
-- 6. search_path -- the mechanism that keeps the toolkit generic
-- ---------------------------------------------------------------------------
-- `toolkit.postgres_store` writes unqualified SQL (`INSERT INTO indicators`),
-- which is deliberate: it is why one module serves every dashboard. The
-- connection supplies the namespace. These are per-role defaults stored in the
-- catalog and applied at connect time -- set once here, never in application
-- code, and inherited by every future connection, cron run, and psql session.
--
-- Order matters. The dashboard's own schema is first, so unqualified writes land
-- there; geo is next for boundary reads; public is last for PostGIS.
ALTER ROLE economy_app   SET search_path = economy, geo, public;
ALTER ROLE education_app SET search_path = education, geo, public;
ALTER ROLE justice_app   SET search_path = justice, geo, public;
ALTER ROLE geo_loader    SET search_path = geo, public;

-- ---------------------------------------------------------------------------
-- 7. geo.boundaries (§4)
-- ---------------------------------------------------------------------------
-- Created empty. No loader writes to it yet -- 901justice holds the only real
-- polygons in the series today (data/boundaries/, eight layers) and there is
-- still no city-limits polygon anywhere, since a union of council districts is
-- not a city boundary. Creating it here rather than later keeps the schema and
-- its one table in the same privileged session.
--
-- **An empty geo.boundaries means "not loaded yet", never "no boundaries
-- exist".** Anything reading it must treat zero rows as a gap, per the
-- honest-gaps invariant -- not as an empty map.
SET ROLE geo_loader;

CREATE TABLE IF NOT EXISTS geo.boundaries (
    boundary_id   BIGSERIAL PRIMARY KEY,
    layer         TEXT NOT NULL,        -- 'municipality' | 'zip' | 'tract'
                                        -- | 'city-council' | 'county-commission'
                                        -- | 'state-house' | 'state-senate' | 'congressional'
    geo_key       TEXT NOT NULL,        -- natural key within the layer: place GEOID
                                        -- '4748000', zip '38114', tract '47157009700'
    name          TEXT NOT NULL,
    geom          geometry(MultiPolygon, 4326) NOT NULL,   -- WGS84, web-map native
    vintage       TEXT NOT NULL,        -- 'TIGER 2024', 'Shelby County GIS 2023-03-11'
    source_url    TEXT,
    retrieved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (layer, geo_key, vintage)    -- re-pulling a vintage is idempotent; a NEW
                                        -- vintage is a new row, so redistricting and
                                        -- annexation keep their history
);

CREATE INDEX IF NOT EXISTS idx_geo_boundaries_layer ON geo.boundaries (layer, geo_key);
CREATE INDEX IF NOT EXISTS idx_geo_boundaries_geom  ON geo.boundaries USING GIST (geom);

RESET ROLE;

-- The table above predates the default privileges in section 5 within this same
-- script's execution order, so grant on it explicitly.
GRANT SELECT ON geo.boundaries TO economy_app, education_app, justice_app;

\echo '== done. Now set passwords: \\password economy_app (and education_app, justice_app, geo_loader) =='
