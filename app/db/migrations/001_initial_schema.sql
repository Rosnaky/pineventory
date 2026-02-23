-- database/migrations/001_initial_schema.sql

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Items table  
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    item_name TEXT NOT NULL,
    quantity_total INTEGER NOT NULL CHECK (quantity_total >= 0),
    quantity_available INTEGER NOT NULL CHECK (quantity_available >= 0),
    location TEXT NOT NULL,
    subteam TEXT NOT NULL,
    point_of_contact BIGINT NOT NULL REFERENCES users(user_id),
    purchase_order TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT quantity_check CHECK (quantity_available <= quantity_total)
);

-- Checkouts table
CREATE TABLE IF NOT EXISTS checkouts (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    checked_out_at TIMESTAMPTZ DEFAULT NOW(),
    expected_return_date TIMESTAMPTZ,
    returned_at TIMESTAMPTZ,
    notes TEXT
);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    action TEXT NOT NULL,
    item_id INTEGER REFERENCES items(id) ON DELETE SET NULL,
    details TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_items_subteam ON items(subteam);

CREATE INDEX IF NOT EXISTS idx_items_location ON items(location);

CREATE INDEX IF NOT EXISTS idx_items_poc ON items(point_of_contact);

CREATE INDEX IF NOT EXISTS idx_checkouts_user ON checkouts(user_id);

CREATE INDEX IF NOT EXISTS idx_checkouts_item ON checkouts(item_id);

CREATE INDEX IF NOT EXISTS idx_checkouts_active ON checkouts(item_id) WHERE returned_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
