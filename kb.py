"""NFL knowledge base — shared read-only access to the local SQLite database.

The KB is a local, gitignored SQLite file built by `kb_build.py` from nflverse
bulk data (1999+). Everything that reads it goes through here, over a **read-only**
connection, so a query can never mutate the data. `kb_query.py` is the CLI; the
agent reads `reference/kb_schema.md` and writes SQL against these tables.

Stdlib only (`sqlite3`).
"""

import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
KB_DIR = os.path.join(DATA, "nfl_kb")          # gitignored — local, derived
DB_PATH = os.path.join(KB_DIR, "nfl.sqlite")
LOCK_PATH = os.path.join(KB_DIR, "sources.lock.json")


def connect_ro(db_path=DB_PATH):
    """Open the KB read-only. Raises a friendly error if it hasn't been built."""
    if not os.path.exists(db_path):
        raise SystemExit(
            f"NFL knowledge base not built yet — run: python3 kb_build.py\n"
            f"(expected DB at {db_path})")
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def query(sql, params=(), db_path=DB_PATH):
    """Run a read-only SQL query; return a list of dict rows."""
    con = connect_ro(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def list_tables(db_path=DB_PATH):
    return [r["name"] for r in query(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        db_path=db_path)]


def columns(table, db_path=DB_PATH):
    return [r["name"] for r in query(f'PRAGMA table_info("{table}")', db_path=db_path)]
