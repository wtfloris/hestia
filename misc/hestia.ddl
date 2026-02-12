-- DROP SCHEMA hestia;

CREATE SCHEMA hestia AUTHORIZATION postgres;

-- DROP SEQUENCE hestia.subscribers_id_seq;

CREATE SEQUENCE hestia.subscribers_id_seq
  INCREMENT BY 1
  MINVALUE 1
  MAXVALUE 2147483647
  START 1
  CACHE 1
  NO CYCLE;
-- DROP SEQUENCE hestia.targets_id_seq;

CREATE SEQUENCE hestia.targets_id_seq
  INCREMENT BY 1
  MINVALUE 1
  MAXVALUE 2147483647
  START 1
  CACHE 1
  NO CYCLE;-- hestia.homes definition

-- Drop table

-- DROP TABLE hestia.homes;

CREATE TABLE hestia.homes (
  url varchar NOT NULL,
  address varchar NOT NULL,
  city varchar NOT NULL,
  price int4 DEFAULT '-1'::integer NOT NULL,
  agency varchar NULL,
  date_added timestamp NOT NULL
);


-- hestia.link_codes definition

-- Drop table

-- DROP TABLE hestia.link_codes;

CREATE TABLE hestia.link_codes (
  code varchar(4) NOT NULL,
  email_address varchar NOT NULL,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP NULL,
  expires_at timestamptz NOT NULL,
  CONSTRAINT link_codes_pkey PRIMARY KEY (code)
);
CREATE INDEX link_codes_email_idx ON hestia.link_codes USING btree (email_address);
CREATE INDEX link_codes_expires_idx ON hestia.link_codes USING btree (expires_at);


-- hestia.magic_tokens definition

-- Drop table

-- DROP TABLE hestia.magic_tokens;

CREATE TABLE hestia.magic_tokens (
  token_id varchar(36) NOT NULL,
  email_address varchar NOT NULL,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP NULL,
  expires_at timestamptz NOT NULL,
  CONSTRAINT magic_tokens_pkey PRIMARY KEY (token_id)
);
CREATE INDEX magic_tokens_email_idx ON hestia.magic_tokens USING btree (email_address);
CREATE INDEX magic_tokens_expires_idx ON hestia.magic_tokens USING btree (expires_at);


-- hestia.meta definition

-- Drop table

-- DROP TABLE hestia.meta;

CREATE TABLE hestia.meta (
  id varchar NOT NULL,
  devmode_enabled bool DEFAULT false NOT NULL,
  scraper_halted bool DEFAULT false NOT NULL,
  workdir varchar NOT NULL,
  donation_link varchar NULL,
  donation_link_updated timestamp NULL
);


-- hestia.preview_cache definition

-- Drop table

-- DROP TABLE hestia.preview_cache;

CREATE TABLE hestia.preview_cache (
  url varchar NOT NULL,
  status varchar NOT NULL,
  image_url varchar NULL,
  image_bytes bytea NULL,
  content_type varchar NULL,
  fetched_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  CONSTRAINT preview_cache_pkey PRIMARY KEY (url)
);
CREATE INDEX preview_cache_expires_idx ON hestia.preview_cache USING btree (expires_at);


-- hestia.subscribers definition

-- Drop table

-- DROP TABLE hestia.subscribers;

CREATE TABLE hestia.subscribers (
  id int4 GENERATED ALWAYS AS IDENTITY( INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START 1 CACHE 1 NO CYCLE) NOT NULL,
  subscription_expiry timestamp DEFAULT '2099-01-01 00:00:00'::timestamp without time zone NULL,
  user_level int4 DEFAULT 0 NOT NULL,
  filter_min_price int4 DEFAULT 500 NOT NULL,
  filter_max_price int4 DEFAULT 2000 NOT NULL,
  filter_cities json DEFAULT '["amsterdam"]'::json NOT NULL,
  telegram_enabled bool DEFAULT false NOT NULL,
  telegram_id varchar NULL,
  filter_agencies json DEFAULT '["woningnet_amsterdam", "woningnet_huiswaarts", "woningnet_bovengroningen", "woningnet_eemvallei", "rebo", "woningnet_groningen", "woningnet_middenholland", "woningnet_woonkeus", "woningnet_woongaard", "krk", "alliantie", "woningnet_utrecht", "nmg", "bouwinvest", "vesteda", "vbt", "woningnet_almere", "woningnet_gooienvecht", "funda", "pararius", "woningnet_mijnwoonservice"]'::json NOT NULL,
  date_added timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
  lang varchar DEFAULT 'en'::character varying NOT NULL,
  email_address varchar NULL
);
CREATE INDEX idx_subscribers_email_address ON hestia.subscribers USING btree (email_address);


-- hestia.targets definition

-- Drop table

-- DROP TABLE hestia.targets;

CREATE TABLE hestia.targets (
  id int4 GENERATED ALWAYS AS IDENTITY( INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START 1 CACHE 1 NO CYCLE) NOT NULL,
  agency varchar NOT NULL,
  queryurl varchar NOT NULL,
  "method" varchar NOT NULL,
  user_info jsonb NOT NULL,
  post_data jsonb DEFAULT '{}'::json NOT NULL,
  headers json DEFAULT '{}'::json NOT NULL,
  enabled bool DEFAULT false NOT NULL
);
