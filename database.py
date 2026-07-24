import sqlite3
import os

DB_FOLDER = "database"
DB_FILE = os.path.join(DB_FOLDER, "subscribers.db")


def init_db():
    os.makedirs(DB_FOLDER, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            phone TEXT,
            state TEXT,
            county TEXT,

            tornado INTEGER DEFAULT 1,
            tornado_emergency INTEGER DEFAULT 1,
            severe INTEGER DEFAULT 1,
            flash_flood INTEGER DEFAULT 1,
            winter INTEGER DEFAULT 0,

            sms INTEGER DEFAULT 1,
            voice INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts(id)
    )
    """)
    conn.commit()
    conn.close()

    print("Database Ready!")
