"""One-off migration: adds the trust_level column to the attachments
table, which already existed before the Security Gateway phase added
TrustLevel. Base.metadata.create_all() only creates missing tables, it
never alters existing ones (see fix_schema.py's docstring for the same
caveat) — so this table needs an explicit ALTER TABLE.

Safe to run multiple times (IF NOT EXISTS). Does not touch any existing
rows/data — every existing attachment just gets trust_level='UNTRUSTED'
via the column default.

Run from the backend/ folder (venv active):

    python -m app.migrate_add_trust_level
"""
from sqlalchemy import text
from .db import engine


def main():
    print("Adding trust_level column to attachments table (if not already present)...")
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE attachments
            ADD COLUMN IF NOT EXISTS trust_level VARCHAR(20) NOT NULL DEFAULT 'UNTRUSTED'
        """))
        conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()