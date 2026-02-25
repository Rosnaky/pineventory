-- database/migrations/003_add_guild_id.sql

-- Add guild_id to items table
ALTER TABLE items
ADD COLUMN guild_id BIGINT NOT NULL DEFAULT 0;

ALTER TABLE checkouts
ADD COLUMN guild_id BIGINT NOT NULL DEFAULT 0;

ALTER TABLE audit_log
ADD COLUMN guild_id BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS guild_permissions (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_permissions_lookup ON guild_permissions(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_guild_permissions_guild ON guild_permissions(guild_id);

ALTER TABLE users DROP COLUMN IF EXISTS is_admin;
