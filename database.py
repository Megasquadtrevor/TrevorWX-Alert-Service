import sqlite3
import os

DB_FOLDER = "database"
DB_FILE = os.path.join(DB_FOLDER, "subscribers.db")


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        # Create the original subscribers table
        conn.execute(SCHEMA)

        # Keep existing subscriber database migrations
        existing = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(subscribers)"
            )
        }

        migrations = {
            "consent":
                "ALTER TABLE subscribers ADD COLUMN consent INTEGER DEFAULT 0",
            "consent_timestamp":
                "ALTER TABLE subscribers ADD COLUMN consent_timestamp TEXT",
            "created_at":
                "ALTER TABLE subscribers ADD COLUMN created_at TEXT",
            "active":
                "ALTER TABLE subscribers ADD COLUMN active INTEGER DEFAULT 1",
        }

        for column, sql in migrations.items():
            if column not in existing:
                conn.execute(sql)

        # Create password reset token table
        conn.execute("""
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
