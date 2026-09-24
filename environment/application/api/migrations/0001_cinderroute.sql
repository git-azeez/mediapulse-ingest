CREATE SCHEMA IF NOT EXISTS cinderroute;

CREATE TABLE IF NOT EXISTS cinderroute.shipments (
    shipment_id UUID PRIMARY KEY,
    owner_id TEXT NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 128),
    reference TEXT NOT NULL CHECK (length(reference) BETWEEN 1 AND 128),
    origin TEXT NOT NULL CHECK (length(origin) BETWEEN 1 AND 256),
    destination TEXT NOT NULL CHECK (length(destination) BETWEEN 1 AND 256),
    version BIGINT NOT NULL CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS shipments_owner_idx
    ON cinderroute.shipments (owner_id, created_at, shipment_id);

CREATE TABLE IF NOT EXISTS cinderroute.events (
    sequence_number BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    shipment_id UUID NOT NULL REFERENCES cinderroute.shipments(shipment_id),
    aggregate_version BIGINT NOT NULL CHECK (aggregate_version >= 1),
    event_type TEXT NOT NULL CHECK (event_type IN ('ShipmentCreated', 'CheckpointRecorded')),
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(idempotency_key) BETWEEN 1 AND 200),
    correlation_id TEXT NOT NULL CHECK (length(correlation_id) BETWEEN 1 AND 200),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (shipment_id, aggregate_version)
);

CREATE INDEX IF NOT EXISTS events_shipment_sequence_idx
    ON cinderroute.events (shipment_id, sequence_number);

CREATE TABLE IF NOT EXISTS cinderroute.outbox (
    event_id UUID PRIMARY KEY REFERENCES cinderroute.events(event_id) ON DELETE CASCADE,
    sequence_number BIGINT NOT NULL UNIQUE,
    payload JSONB NOT NULL,
    published_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS outbox_pending_idx
    ON cinderroute.outbox (sequence_number)
    WHERE published_at IS NULL;

CREATE TABLE IF NOT EXISTS cinderroute.audit_archives (
    event_id UUID PRIMARY KEY REFERENCES cinderroute.events(event_id) ON DELETE CASCADE,
    object_key TEXT NOT NULL,
    archived_at TIMESTAMPTZ NOT NULL
);
