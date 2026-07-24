import sqlite3
import os

DB_FOLDER = "database"
DB_FILE = os.path.join(DB_FOLDER, "subscribers.db")

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

conn.commit()
conn.close()

print("Database Ready!")