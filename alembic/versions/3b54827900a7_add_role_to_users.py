"""add role to users

Revision ID: 3b54827900a7
Revises: 0268cfe1cbff
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa

revision = '3b54827900a7'
down_revision = '0268cfe1cbff'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=True))
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
    op.alter_column('users', 'role', nullable=False)

def downgrade():
    op.drop_column('users', 'role')
