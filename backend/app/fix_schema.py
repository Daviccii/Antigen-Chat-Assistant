"""
One-off fix for schema drift: conversations/messages/memories tables were
created before user_id (and other columns) were added to models.py.
Base.metadata.create_all() only creates missing tables, it never alters
existing ones, so those tables are stuck on an old schema.

This drops just those three tables and lets init_db() recreate them from
the current models.py. Safe for dev: it reuses the app's own configured
engine, so no DB credentials needed here, and it does NOT touch the users
table — your account is untouched.

Run from the backend/ folder (with your venv active) as a module so the
relative imports in app/db.py and app/models.py resolve correctly:

    python -m app.fix_schema
"""
from sqlalchemy import text
from .db import engine, init_db

TABLES_TO_RESET = ["messages", "conversations", "memories"]


def main():
    print("Dropping out-of-date tables:", ", ".join(TABLES_TO_RESET))
    with engine.connect() as conn:
        for table in TABLES_TO_RESET:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        conn.commit()
    print("Dropped. Recreating tables from current models.py...")
    init_db()
    print("Done. conversations/messages/memories now match models.py.")


if __name__ == "__main__":
    main()