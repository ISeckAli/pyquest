"""Add guest flag to people

Revision ID: 3bd78781b334
Revises: 2a8a78d9c875
Create Date: 2026-09-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3bd78781b334'
down_revision = '2a8a78d9c875'
branch_labels = None
depends_on = None


def upgrade():
    # sa.false() rather than sa.text('0'): SQLite accepts 0 as false, but
    # Postgres rejects a number as the default of a true/false column.
    # sa.false() is written the right way for whichever database runs this.
    with op.batch_alter_table('person', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_guest', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('person', schema=None) as batch_op:
        batch_op.drop_column('is_guest')