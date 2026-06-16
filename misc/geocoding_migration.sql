-- Adds geocoding columns and a radius filter to Hestia.
-- Safe to run multiple times: uses IF NOT EXISTS where possible.

-- Coordinates and confidence on scraped homes. NULL = not yet geocoded or lookup failed.
ALTER TABLE hestia.homes
  ADD COLUMN IF NOT EXISTS lat double precision NULL,
  ADD COLUMN IF NOT EXISTS lon double precision NULL,
  ADD COLUMN IF NOT EXISTS geocode_confidence real NULL;

CREATE INDEX IF NOT EXISTS homes_latlon_idx
  ON hestia.homes USING btree (lat, lon);

-- Subscriber-level radius filter. NULL radius = filter disabled.
ALTER TABLE hestia.subscribers
  ADD COLUMN IF NOT EXISTS filter_center_lat double precision NULL,
  ADD COLUMN IF NOT EXISTS filter_center_lon double precision NULL,
  ADD COLUMN IF NOT EXISTS filter_radius_km real NULL;

-- Geocode cache keyed on (address, city). Avoids hammering PDOK for repeat addresses.
CREATE TABLE IF NOT EXISTS hestia.geocode_cache (
  address varchar NOT NULL,
  city varchar NOT NULL,
  lat double precision NULL,
  lon double precision NULL,
  confidence real NULL,
  fetched_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT geocode_cache_pkey PRIMARY KEY (address, city)
);
