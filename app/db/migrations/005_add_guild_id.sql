
CREATE INDEX IF NOT EXISTS idx_items_guild ON items(guild_id);
CREATE INDEX IF NOT EXISTS idx_checkouts_guild ON checkouts(guild_id);
CREATE INDEX IF NOT EXISTS idx_audit_guild ON audit_log(guild_id);
