"""enhance_memory_model_phase3

Revision ID: 1204376b19dc
Revises: 91504e0afc1c
Create Date: 2026-08-25 15:19:52.676261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '1204376b19dc'
down_revision: Union[str, Sequence[str], None] = '91504e0afc1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Phase 3 memory enhancements."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # === Create projects table ===
    if 'projects' not in inspector.get_table_names():
        op.create_table('projects',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)
        op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=False)
        op.create_index(op.f('ix_projects_user_id'), 'projects', ['user_id'], unique=False)
    
    # === Enhance memories table ===
    if 'memories' in inspector.get_table_names():
        # Add new memory metadata columns
        new_columns = [
            ('category', sa.String(length=64), True),
            ('importance', sa.String(length=20), True),
            ('confidence', sa.Float(), True),
            ('status', sa.String(length=20), True),
            ('project_id', sa.Integer(), True),
            ('last_accessed_at', sa.DateTime(), True),
            ('last_confirmed_at', sa.DateTime(), True),
            ('extra_metadata', sa.Text(), True),
        ]
        
        for column_name, column_type, nullable in new_columns:
            try:
                # Check if column already exists
                columns = [col['name'] for col in inspector.get_columns('memories')]
                if column_name not in columns:
                    op.add_column('memories', sa.Column(column_name, column_type, nullable=nullable))
                    # Set default values for existing rows
                    if column_name == 'importance':
                        conn.execute(text("UPDATE memories SET importance = 'NORMAL' WHERE importance IS NULL"))
                    elif column_name == 'confidence':
                        conn.execute(text("UPDATE memories SET confidence = 0.5 WHERE confidence IS NULL"))
                    elif column_name == 'status':
                        conn.execute(text("UPDATE memories SET status = 'ACTIVE' WHERE status IS NULL"))
                    conn.commit()
            except Exception as e:
                print(f"Warning: Could not add column {column_name}: {e}")
                conn.rollback()
        
        # Add foreign key for project_id if it doesn't exist
        try:
            # Check if foreign key already exists
            foreign_keys = inspector.get_foreign_keys('memories')
            fk_exists = any(fk.get('constrained_columns') == ['project_id'] for fk in foreign_keys)
            if not fk_exists:
                op.create_foreign_key('fk_memories_project_id', 'memories', 'projects', ['project_id'], ['id'], ondelete='SET NULL')
        except Exception as e:
            print(f"Warning: Could not create foreign key for project_id: {e}")
        
        # Create new indexes
        new_indexes = [
            ('ix_memories_category', 'category'),
            ('ix_memories_project_id', 'project_id'),
            ('ix_memories_importance', 'importance'),
            ('ix_memories_status', 'status'),
            ('ix_memories_source', 'source'),
        ]
        
        for index_name, column_name in new_indexes:
            try:
                # Check if index already exists
                existing_indexes = inspector.get_indexes('memories')
                index_names = [idx['name'] for idx in existing_indexes]
                if index_name not in index_names:
                    op.create_index(index_name, 'memories', [column_name])
            except Exception as e:
                print(f"Warning: Could not create index {index_name}: {e}")


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Remove foreign key first
    try:
        op.drop_constraint('fk_memories_project_id', 'memories', type_='foreignkey')
    except Exception:
        pass
    
    # Drop new indexes
    try:
        op.drop_index('ix_memories_source', table_name='memories')
    except Exception:
        pass
    try:
        op.drop_index('ix_memories_status', table_name='memories')
    except Exception:
        pass
    try:
        op.drop_index('ix_memories_importance', table_name='memories')
    except Exception:
        pass
    try:
        op.drop_index('ix_memories_project_id', table_name='memories')
    except Exception:
        pass
    try:
        op.drop_index('ix_memories_category', table_name='memories')
    except Exception:
        pass
    
    # Drop new columns
    new_columns = ['extra_metadata', 'last_confirmed_at', 'last_accessed_at', 'project_id', 'status', 'confidence', 'importance', 'category']
    for column_name in new_columns:
        try:
            op.drop_column('memories', column_name)
        except Exception:
            pass
    
    # Drop projects table if it exists
    if 'projects' in inspector.get_table_names():
        try:
            op.drop_index(op.f('ix_projects_user_id'), table_name='projects')
        except Exception:
            pass
        try:
            op.drop_index(op.f('ix_projects_name'), table_name='projects')
        except Exception:
            pass
        try:
            op.drop_index(op.f('ix_projects_id'), table_name='projects')
        except Exception:
            pass
        try:
            op.drop_table('projects')
        except Exception:
            pass
