"""One-off migration: adds trading_enabled to the existing
security_settings table. Same situation as migrate_add_trust_level.py —
create_all() won't alter a table that already exists.

Run from the backend/ folder (venv active):

    python -m app.migrate_add_trading_enabled
"""
from sqlalchemy import text
from .db import engine


def main():
    print("Adding trading_enabled column to security_settings table (if not already present)...")
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE security_settings
            ADD COLUMN IF NOT EXISTS trading_enabled BOOLEAN NOT NULL DEFAULT FALSE
        """))
        conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()s