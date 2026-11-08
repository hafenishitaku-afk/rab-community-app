import sqlite3
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "community.db"

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def db():
    """Connect to PostgreSQL (Render) or SQLite (Local)."""
    db_url = os.environ.get("DATABASE_URL")
    
    if db_url:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        conn = sqlite3.connect(DB, timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = dict_factory
        return conn

def execute_query(cursor, query, params=None):
    """Automatically convert ? to %s for Postgres."""
    if os.environ.get("DATABASE_URL"):
        query = query.replace("?", "%s")
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor


def init_db():
    """Create tables for Community App."""
    conn = db()
    c = conn.cursor()
    is_postgres = os.environ.get("DATABASE_URL") is not None
    
    if is_postgres:
        execute_query(c, """
            CREATE TABLE IF NOT EXISTS users(
                id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                location TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'staff',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query(c, """
            CREATE TABLE IF NOT EXISTS messages(
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # ✅ NEW: Voice Notes Table
        execute_query(c, """
            CREATE TABLE IF NOT EXISTS voice_notes(
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    else:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                location TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'staff',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS voice_notes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        
    conn.commit()
    conn.close()
    print("✅ Community Database initialized.")