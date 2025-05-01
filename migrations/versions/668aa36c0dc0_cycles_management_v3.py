"""Cycles Management v3

Revision ID: 668aa36c0dc0
Revises: 30dcade7eaa7
Create Date: 2025-04-22 20:41:10.609874

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '668aa36c0dc0'
down_revision = '30dcade7eaa7'
branch_labels = None
depends_on = None


def upgrade():
    # Add each column individually without foreign key constraints
    op.add_column('sprint_project_map', sa.Column('status_comment', sa.Text(), nullable=True))
    op.add_column('sprint_project_map', sa.Column('status_updated', sa.DateTime(), nullable=True))
    op.add_column('sprint_project_map', sa.Column('status_updated_by', sa.Integer(), nullable=True))
    
    # The foreign key relationship will be maintained at the application level
    # We won't try to add the foreign key constraint directly in SQLite

def downgrade():
    # Drop columns in reverse order
    op.drop_column('sprint_project_map', 'status_updated_by')
    op.drop_column('sprint_project_map', 'status_updated')
    op.drop_column('sprint_project_map', 'status_comment')
    
    
# ### end Alembic commands ###
