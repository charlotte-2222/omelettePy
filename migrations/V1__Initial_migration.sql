-- Revises: V0
-- Creation Date: 2024-12-19
-- Reason: Initial migration

CREATE TABLE IF NOT EXISTS tags
(
    id          SERIAL PRIMARY KEY,
    name        TEXT,
    content     TEXT,
    owner_id    BIGINT,
    uses        INTEGER   DEFAULT (0),
    location_id BIGINT,
    created_at  TIMESTAMP DEFAULT (now() at time zone 'utc')
);

CREATE INDEX IF NOT EXISTS tags_name_idx ON tags (name);
CREATE INDEX IF NOT EXISTS tags_location_id_idx ON tags (location_id);
CREATE INDEX IF NOT EXISTS tags_name_trgm_idx ON tags USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS tags_name_lower_idx ON tags (LOWER(name));
CREATE UNIQUE INDEX IF NOT EXISTS tags_uniq_idx ON tags (LOWER(name), location_id);

CREATE TABLE IF NOT EXISTS tag_lookup
(
    id          SERIAL PRIMARY KEY,
    name        TEXT,
    location_id BIGINT,
    owner_id    BIGINT,
    created_at  TIMESTAMP DEFAULT (now() at time zone 'utc'),
    tag_id      INTEGER REFERENCES tags (id) ON DELETE CASCADE ON UPDATE NO ACTION
);

CREATE INDEX IF NOT EXISTS tag_lookup_name_idx ON tag_lookup (name);
CREATE INDEX IF NOT EXISTS tag_lookup_location_id_idx ON tag_lookup (location_id);
CREATE INDEX IF NOT EXISTS tag_lookup_name_trgm_idx ON tag_lookup USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS tag_lookup_name_lower_idx ON tag_lookup (LOWER(name));
CREATE UNIQUE INDEX IF NOT EXISTS tag_lookup_uniq_idx ON tag_lookup (LOWER(name), location_id);


CREATE TABLE IF NOT EXISTS rtfm
(
    id      SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE,
    count   INTEGER DEFAULT (1)
);

CREATE INDEX IF NOT EXISTS rtfm_user_id_idx ON rtfm (user_id);
CREATE INDEX IF NOT EXISTS reminders_expires_idx ON reminders (expires);
CREATE TABLE IF NOT EXISTS command_config
(
    id         SERIAL PRIMARY KEY,
    guild_id   BIGINT,
    channel_id BIGINT,
    name       TEXT,
    whitelist  BOOLEAN
);

CREATE INDEX IF NOT EXISTS command_config_guild_id_idx ON command_config (guild_id);