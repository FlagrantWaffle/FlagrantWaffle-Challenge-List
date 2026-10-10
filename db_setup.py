from db import get_connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,

    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    levels_reviewed INTEGER NOT NULL DEFAULT 0,

    discord_id TEXT NOT NULL UNIQUE,
    discord_username TEXT,
    discord_display_name TEXT,
    discord_avatar_hash TEXT
);



CREATE TABLE IF NOT EXISTS levels (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    gd_id INTEGER NOT NULL UNIQUE,
    creator TEXT NOT NULL,
    rank INTEGER,
    points INTEGER,
    verification_url TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);


CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id INTEGER NOT NULL,
    level_id INTEGER NOT NULL,

    proof_url TEXT NOT NULL,

    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    status TEXT NOT NULL DEFAULT 'pending',

    moderator_comment TEXT,

    reviewed_at TIMESTAMPTZ,
    reviewed_by INTEGER,

    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (level_id) REFERENCES levels(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id),

    CHECK (status IN ('pending', 'approved', 'denied'))
);


CREATE UNIQUE INDEX IF NOT EXISTS unique_pending_submission_per_level
ON submissions (user_id, level_id)
WHERE status = 'pending';


CREATE TABLE IF NOT EXISTS completions (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id INTEGER NOT NULL,
    level_id INTEGER NOT NULL,
    submission_id INTEGER NOT NULL UNIQUE,

    proof_url TEXT NOT NULL,

    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (level_id) REFERENCES levels(id),
    FOREIGN KEY (submission_id) REFERENCES submissions(id),

    UNIQUE (user_id, level_id)
);
"""


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)


if __name__ == "__main__":
    init_db()
    print("database initialised.")