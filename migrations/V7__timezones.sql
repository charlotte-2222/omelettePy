-- Revises: V6
-- Creation Date: 2024-12-19
-- Reason: timezones

CREATE TABLE IF NOT EXISTS user_settings
(
    id       BIGINT PRIMARY KEY, -- The discord user ID
    timezone TEXT                -- The user's timezone
);

ALTER TABLE reminders
    ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC';