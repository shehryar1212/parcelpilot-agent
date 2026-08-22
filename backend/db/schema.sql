-- ParcelPilot Agent – schema
-- Run against local Postgres for dev, and against Neon for the hosted version.
-- Idempotent: safe to re-run.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

-- ---------------------------------------------------------------------------
-- Structured operational data (from ParcelPilot_Assessment_Data.xlsx)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS accounts (
    account_id       TEXT PRIMARY KEY,
    account_name     TEXT NOT NULL,
    plan             TEXT NOT NULL CHECK (plan IN ('Enterprise', 'Growth', 'Standard')),
    status           TEXT NOT NULL,
    csm              TEXT,
    contract_file    TEXT,               -- filename in doc_chunks.source_file, nullable
    premium_support  BOOLEAN NOT NULL DEFAULT FALSE,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    order_id                   TEXT PRIMARY KEY,
    account_id                 TEXT NOT NULL REFERENCES accounts(account_id),
    carrier                    TEXT NOT NULL,
    status                     TEXT NOT NULL CHECK (status IN ('DRAFT', 'BOOKED', 'PICKED_UP', 'DELIVERED', 'CANCELLED')),
    booked_at                  TIMESTAMP NOT NULL,
    pickup_window_start        TIMESTAMP NOT NULL,
    pickup_window_end          TIMESTAMP NOT NULL,
    pickup_actual_at           TIMESTAMP,
    shipment_fee_inr           NUMERIC(10, 2) NOT NULL,
    carrier_fault              BOOLEAN NOT NULL DEFAULT FALSE,
    customer_fault             BOOLEAN NOT NULL DEFAULT FALSE,
    cancellation_requested_at  TIMESTAMP,
    notes                      TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_account ON orders(account_id);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id                 TEXT PRIMARY KEY,
    account_id                TEXT NOT NULL REFERENCES accounts(account_id),
    created_at                TIMESTAMP NOT NULL,
    status                    TEXT NOT NULL,
    subject                   TEXT NOT NULL,
    description               TEXT NOT NULL,
    channel                   TEXT,
    assigned_to               TEXT,
    last_customer_message_at  TIMESTAMP,
    -- Deliberately NOT authoritative – see agent/system prompt. Historical
    -- resolutions may be wrong (this is the whole point of the dataset).
    historical_resolution     TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_account ON tickets(account_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

-- ---------------------------------------------------------------------------
-- Document chunks (from the 6 PDFs), chunked by the document's own numbered
-- sections – see backend/db/chunk_documents.py for rationale.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS doc_chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file         TEXT NOT NULL,
    doc_type            TEXT NOT NULL CHECK (doc_type IN ('policy', 'sop', 'product_doc', 'contract')),
    -- 'current' / 'deprecated' for policy docs, 'active' for contracts.
    status              TEXT NOT NULL,
    -- NULL = applies to all customers. Set = customer-specific contract.
    customer_account_id TEXT REFERENCES accounts(account_id),
    effective_date      DATE,
    section_number      TEXT,
    section_title       TEXT NOT NULL,
    content             TEXT NOT NULL,
    -- text-embedding-3-small = 1536 dims. Change this (and re-embed) if you
    -- switch embedding models – dimension must match exactly.
    embedding           VECTOR(1536),
    created_at          TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_type_status ON doc_chunks(doc_type, status);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_account ON doc_chunks(customer_account_id);
-- Vector index added after data is loaded (see chunk_documents.py note) –
-- IVFFlat needs rows present to pick good list counts, and with ~25 rows
-- total here a sequential scan is actually faster than an ANN index anyway.

-- ---------------------------------------------------------------------------
-- Mocked state-changing actions (the "action tool"). Two-phase: a row is
-- inserted as pending_confirmation by prepare_action, and only flips to
-- executed once the user explicitly confirms via execute_action.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_actions (
    action_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type     TEXT NOT NULL CHECK (action_type IN ('escalation', 'ticket_update', 'follow_up_task', 'cancellation_request')),
    account_id      TEXT NOT NULL REFERENCES accounts(account_id),
    ticket_id       TEXT REFERENCES tickets(ticket_id),
    -- Mocked session identity – e.g. 'customer:ACCT-002' or 'staff:rohit'.
    requested_by    TEXT NOT NULL,
    payload         JSONB NOT NULL,      -- e.g. {"new_severity": "P1", "note": "..."}
    preview_text    TEXT NOT NULL,       -- human-readable summary shown for confirmation
    status          TEXT NOT NULL DEFAULT 'pending_confirmation'
                        CHECK (status IN ('pending_confirmation', 'executed', 'cancelled', 'expired')),
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    executed_at     TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_actions_status ON agent_actions(status);

-- ---------------------------------------------------------------------------
-- Dataset reference metadata (from the xlsx README sheet). This is data-pack
-- metadata, not an agent-computed answer – used as "now" for all time math.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dataset_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
INSERT INTO dataset_meta (key, value) VALUES
    ('snapshot_at', '2026-08-16 11:00:00'),
    ('snapshot_timezone', 'Asia/Kolkata'),
    ('currency', 'INR')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
