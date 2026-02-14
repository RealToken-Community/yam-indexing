-- init_postgres/00-init.sql
-- Creates tables + roles + privileges for yam_events.
-- Runs automatically on first DB initialization (empty data dir).

-- -----------------------------
-- 1) Create roles (users)
-- Passwords are set in 01-passwords.sql (generated from env)
-- -----------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yam-indexing-writer') THEN
    CREATE ROLE "yam-indexing-writer" LOGIN;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yam-indexing-reader') THEN
    CREATE ROLE "yam-indexing-reader" LOGIN;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yam-indexing-event_queue') THEN
    CREATE ROLE "yam-indexing-event_queue" LOGIN;
  END IF;
END
$$;

-- -----------------------------
-- 2) Create tables (Postgres equivalent of SQLite init_db)
-- -----------------------------

CREATE TABLE IF NOT EXISTS public.offers (
  offer_id            BIGINT PRIMARY KEY,
  seller_address      TEXT NOT NULL,
  initial_amount      TEXT NOT NULL,
  price_per_unit      TEXT NOT NULL,
  offer_token         TEXT NOT NULL,
  buyer_token         TEXT NOT NULL,
  status              TEXT NOT NULL DEFAULT 'InProgress'
                       CHECK (status IN ('InProgress', 'SoldOut', 'Deleted')),
  block_number        BIGINT NOT NULL,
  transaction_hash    TEXT NOT NULL,
  log_index           INT NOT NULL,
  creation_timestamp  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.offer_events (
  offer_id            BIGINT NOT NULL,
  event_type          TEXT NOT NULL
                       CHECK (event_type IN ('OfferCreated', 'OfferUpdated', 'OfferAccepted', 'OfferDeleted')),
  amount              TEXT,
  price               TEXT,
  buyer_address       TEXT,
  amount_bought       TEXT,
  block_number        BIGINT NOT NULL,
  transaction_hash    TEXT NOT NULL,
  log_index           INT NOT NULL,
  price_bought        TEXT,
  event_timestamp     TIMESTAMPTZ,
  unique_id           TEXT PRIMARY KEY NOT NULL,
  CONSTRAINT fk_offer_events_offer
    FOREIGN KEY (offer_id) REFERENCES public.offers (offer_id)
);

CREATE TABLE IF NOT EXISTS public.indexing_state (
  indexing_id   BIGSERIAL PRIMARY KEY,
  from_block    BIGINT NOT NULL,
  to_block      BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.event_queue (
  id            BIGSERIAL PRIMARY KEY,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload       JSONB NOT NULL
);

-- -----------------------------
-- 3) Create indexes
-- -----------------------------

-- Composite index for offer_events filtering
CREATE INDEX IF NOT EXISTS idx_offer_events_type_timestamp
  ON public.offer_events (event_type, event_timestamp);

-- Index for buyer address filtering
CREATE INDEX IF NOT EXISTS idx_offer_events_buyer_address
  ON public.offer_events (buyer_address);

-- Index for seller address filtering
CREATE INDEX IF NOT EXISTS idx_offers_seller_address
  ON public.offers (seller_address);

-- Foreign key index for JOIN optimization
CREATE INDEX IF NOT EXISTS idx_offer_events_offer_id
  ON public.offer_events (offer_id);

-- -----------------------------
-- 4) Privileges
-- -----------------------------

-- Allow DB connection
GRANT CONNECT ON DATABASE yam_events TO "yam-indexing-writer";
GRANT CONNECT ON DATABASE yam_events TO "yam-indexing-reader";
GRANT CONNECT ON DATABASE yam_events TO "yam-indexing-event_queue";

-- Allow schema usage
GRANT USAGE ON SCHEMA public TO "yam-indexing-writer";
GRANT USAGE ON SCHEMA public TO "yam-indexing-reader";
GRANT USAGE ON SCHEMA public TO "yam-indexing-event_queue";

-- Writer: full rights on all current tables + sequences
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "yam-indexing-writer";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "yam-indexing-writer";

-- Ensure writer gets rights on future tables/sequences too
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "yam-indexing-writer";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO "yam-indexing-writer";

-- Reader: read-only on all current tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "yam-indexing-reader";

-- Ensure reader gets SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO "yam-indexing-reader";

-- event_queue user: ONLY privileges on event_queue (and its sequence)
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM "yam-indexing-event_queue";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM "yam-indexing-event_queue";

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.event_queue TO "yam-indexing-event_queue";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.event_queue_id_seq TO "yam-indexing-event_queue";

-- Read-only access on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "yam-indexing-event_queue";

-- Ensure read-only access on future tables as well
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO "yam-indexing-event_queue";

-- prevent random role from creating tables in public schema
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CREATE ON SCHEMA public TO postgres;