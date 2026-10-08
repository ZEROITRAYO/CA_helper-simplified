"""remove the 48-hour expiry of CA requests

Revision ID: 5e2a9d7c1b64
Revises: 3b8f6c2d9e41
Create Date: 2026-10-08 12:00:00

A request now stays open until the CA accepts or declines it or the business withdraws it.
Requests that had expired become "cancelled". The news monitor's four tables stay in the
database, unused (migrations/env.py tells `flask db check` to ignore them).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5e2a9d7c1b64'
down_revision = '3b8f6c2d9e41'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE engagements SET status = 'cancelled' WHERE status = 'expired'")
    op.drop_column('engagements', 'expires_at')


def downgrade():
    # The column comes back empty; cancelled requests stay cancelled.
    op.add_column(
        'engagements', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True)
    )
