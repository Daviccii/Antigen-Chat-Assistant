"""add_timezone_to_users

Revision ID: 91504e0afc1c
Revises: 
Create Date: 2026-08-25 14:58:29.216402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91504e0afc1c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if users table exists before adding the column
    # This handles the case where the database is being initialized for the first time
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'users' in inspector.get_table_names():
        # Add timezone column to existing users table
        # First make it nullable to update existing rows, then make it non-nullable
        try:
            op.add_column('users', sa.Column('timezone', sa.String(length=50), nullable=True, server_default='Africa/Nairobi'))
            
            # Update existing rows to have the default timezone
            conn.execute(sa.text("UPDATE users SET timezone = 'Africa/Nairobi' WHERE timezone IS NULL"))
            conn.commit()
            
            # Now make the column non-nullable
            op.alter_column('users', 'timezone', nullable=False)
        except Exception:
            # Column might already exist, which is fine
            pass
    
    # Handle pgvector column conversion if memories table exists
    if 'memories' in inspector.get_table_names():
        try:
            # Convert embedding column from VECTOR to TEXT if it exists as VECTOR
            conn.execute(sa.text("ALTER TABLE memories ALTER COLUMN embedding TYPE TEXT USING embedding::text"))
            conn.commit()
        except Exception:
            # Column might already be TEXT or doesn't exist, which is fine
            pass


def downgrade() -> None:
    """Downgrade schema."""
    # Remove timezone column from users table
    try:
        op.drop_column('users', 'timezone')
    except Exception:
        # Column might not exist, which is fine
        pass
