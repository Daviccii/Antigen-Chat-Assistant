"""fix_embedding_column_to_vector

Revision ID: ad6b87ed080c
Revises: 1204376b19dc
Create Date: 2026-08-27 14:41:42.989660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'ad6b87ed080c'
down_revision: Union[str, Sequence[str], None] = '1204376b19dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Fix embedding column to use proper pgvector type."""
    conn = op.get_bind()
    
    # Check if vector extension is available
    try:
        conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        vector_available = True
    except Exception:
        vector_available = False
    
    if vector_available:
        # Directly alter the column type from TEXT to VECTOR
        # Since embedding is currently NULL for all rows, we can safely convert
        conn.execute(text("ALTER TABLE memories ALTER COLUMN embedding TYPE vector(768) USING NULL::vector(768)"))
        conn.commit()
    else:
        # If vector extension is not available, keep as TEXT but log warning
        print("Warning: pgvector extension not available, keeping embedding as TEXT")


def downgrade() -> None:
    """Downgrade schema - Convert embedding back to TEXT."""
    conn = op.get_bind()
    
    # Change back to TEXT 
    conn.execute(text("ALTER TABLE memories ALTER COLUMN embedding TYPE text"))
    conn.commit()
