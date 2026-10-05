from db import get_connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE
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

INSERT INTO levels (
    name,
    gd_id,
    creator,
    rank,
    points,
    verification_url) VALUES (
    'TEST',
    123,
    'FlagrantWaffle',
    999,
    0,
    'https://www.youtube.com/watch?v=YAgJ9XugGBo&list=RDYAgJ9XugGBo&start_radio=1')
    ON CONFLICT (gd_id) DO NOTHING;
    

    
CREATE TABLE IF NOT EXISTS completions (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER NOT NULL,
    level_id INTEGER NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (level_id) REFERENCES levels(id),

    UNIQUE (user_id, level_id)
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


"""


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)


if __name__ == "__main__":
    init_db()
    print("database initialised.")