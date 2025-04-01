-- Revises: V6
-- Creation Date: 2024-12-19
-- Reason: timezones

CREATE TABLE IF NOT EXISTS user_settings
(
    id       BIGINT PRIMARY KEY, -- The discord user ID
    timezone TEXT,                -- The user's timezone
    github_username VARCHAR(39), -- user's github name
    allow_mentions BOOLEAN DEFAULT true -- mentions
);

ALTER TABLE reminders
    ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC';
    CREATE INDEX idx_github_username ON user_settings(github_username);