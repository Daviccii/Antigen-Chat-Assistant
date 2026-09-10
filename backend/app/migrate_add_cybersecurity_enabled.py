"""One-off migration: adds cybersecurity_enabled to the existing
security_settings table.

Run from the backend/ folder (venv active):

    python -m app.migrate_add_cybersecurity_enabled
"""
from sqlalchemy import text
from .db import engine


def main():
    print("Adding cybersecurity_enabled column to security_settings table (if not already present)...")
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE security_settings
            ADD COLUMN IF NOT EXISTS cybersecurity_enabled BOOLEAN NOT NULL DEFAULT FALSE
        """))
        conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()