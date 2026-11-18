"""Persistência do histórico de conversas em SQLite."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "inframind.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        );
    """)
    return conn


def list_conversations(username, limit=30):
    with _conn() as c:
        return c.execute("SELECT id, title FROM conversations WHERE username=? ORDER BY updated_at DESC, id DESC LIMIT ?",
                         (username, limit)).fetchall()


def create_conversation(username, title):
    with _conn() as c:
        return c.execute("INSERT INTO conversations (username, title) VALUES (?, ?)", (username, title[:60])).lastrowid


def get_messages(conversation_id, username):
    with _conn() as c:
        return [{"role": r, "content": t} for r, t in c.execute(
            "SELECT m.role, m.content FROM messages m JOIN conversations v ON v.id=m.conversation_id "
            "WHERE m.conversation_id=? AND v.username=? ORDER BY m.id", (conversation_id, username))]


def add_message(conversation_id, role, content):
    with _conn() as c:
        c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)", (conversation_id, role, content))
        c.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (conversation_id,))


def delete_conversation(conversation_id, username):
    with _conn() as c:
        c.execute("DELETE FROM conversations WHERE id=? AND username=?", (conversation_id, username))


def delete_all(username):
    with _conn() as c:
        c.execute("DELETE FROM conversations WHERE username=?", (username,))
