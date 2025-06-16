--
-- PostgreSQL database dump
--

-- Dumped from database version 15.6 (Debian 15.6-1.pgdg120+2)
-- Dumped by pg_dump version 15.6 (Debian 15.6-1.pgdg120+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: hestia; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA hestia;


ALTER SCHEMA hestia OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: homes; Type: TABLE; Schema: hestia; Owner: postgres
--

CREATE TABLE hestia.homes (
    url character varying NOT NULL,
    address character varying NOT NULL,
    city character varying NOT NULL,
    price integer DEFAULT '-1'::integer NOT NULL,
    agency character varying,
    date_added timestamp without time zone NOT NULL
);


ALTER TABLE hestia.homes OWNER TO postgres;

--
-- Name: meta; Type: TABLE; Schema: hestia; Owner: postgres
--

CREATE TABLE hestia.meta (
    id character varying NOT NULL,
    devmode_enabled boolean DEFAULT false NOT NULL,
    scraper_halted boolean DEFAULT false NOT NULL,
    workdir character varying NOT NULL,
    donation_link character varying,
    donation_link_updated timestamp without time zone
);


ALTER TABLE hestia.meta OWNER TO postgres;

--
-- Name: subscribers; Type: TABLE; Schema: hestia; Owner: postgres
--

CREATE TABLE hestia.subscribers (
    id integer NOT NULL,
    subscription_expiry timestamp without time zone DEFAULT '2099-01-01 00:00:00'::timestamp without time zone,
    user_level integer DEFAULT 0 NOT NULL,
    filter_min_price integer DEFAULT 500 NOT NULL,
    filter_max_price integer DEFAULT 2000 NOT NULL,
    filter_cities json DEFAULT '["amsterdam"]'::json NOT NULL,
    telegram_enabled boolean DEFAULT false NOT NULL,
    telegram_id character varying,
    filter_agencies json DEFAULT '[]'::json NOT NULL,
    date_added timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

ALTER TABLE hestia.subscribers
    ADD COLUMN response_template TEXT;

ALTER TABLE hestia.subscribers OWNER TO postgres;

--
-- Name: subscribers_id_seq; Type: SEQUENCE; Schema: hestia; Owner: postgres
--

ALTER TABLE hestia.subscribers ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME hestia.subscribers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: targets; Type: TABLE; Schema: hestia; Owner: postgres
--

CREATE TABLE hestia.targets (
    id integer NOT NULL,
    agency character varying NOT NULL,
    queryurl character varying NOT NULL,
    method character varying NOT NULL,
    user_info json NOT NULL,
    post_data json DEFAULT '{}'::json NOT NULL,
    headers json DEFAULT '{}'::json NOT NULL,
    enabled boolean DEFAULT false NOT NULL
);


ALTER TABLE hestia.targets OWNER TO postgres;

--
-- Name: targets_id_seq; Type: SEQUENCE; Schema: hestia; Owner: postgres
--

ALTER TABLE hestia.targets ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME hestia.targets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: SCHEMA hestia; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA hestia TO hestia;


--
-- Name: TABLE homes; Type: ACL; Schema: hestia; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE hestia.homes TO hestia;


--
-- Name: TABLE meta; Type: ACL; Schema: hestia; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE hestia.meta TO hestia;


--
-- Name: TABLE subscribers; Type: ACL; Schema: hestia; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE hestia.subscribers TO hestia;


--
-- Name: TABLE targets; Type: ACL; Schema: hestia; Owner: postgres
--

GRANT SELECT ON TABLE hestia.targets TO hestia;


--
-- PostgreSQL database dump complete
--
