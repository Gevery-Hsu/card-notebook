CREATE TABLE IF NOT EXISTS notebook_settings (
    id integer PRIMARY KEY CHECK (id=1),
    categories bytea NOT NULL
);
CREATE TABLE IF NOT EXISTS notebook_notes (
    id uuid PRIMARY KEY,
    filename text NOT NULL UNIQUE,
    raw bytea NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    category text NOT NULL,
    tags text[] NOT NULL DEFAULT '{}',
    source text NOT NULL DEFAULT '',
    source_url text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    trashed boolean NOT NULL DEFAULT false,
    version uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS notebook_notes_date ON notebook_notes (trashed,created_at,id);
CREATE INDEX IF NOT EXISTS notebook_notes_category ON notebook_notes (category);
CREATE INDEX IF NOT EXISTS notebook_notes_tags ON notebook_notes USING gin (tags);
CREATE TABLE IF NOT EXISTS notebook_sessions (
    token_hash text PRIMARY KEY,
    key_id text NOT NULL,
    expires bigint NOT NULL,
    created bigint NOT NULL
);
CREATE TABLE IF NOT EXISTS notebook_login_limits (
    bucket text PRIMARY KEY,
    attempts integer NOT NULL,
    reset_at bigint NOT NULL
);
