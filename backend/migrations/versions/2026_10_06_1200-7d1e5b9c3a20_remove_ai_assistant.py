"""remove the AI assistant's tables

Revision ID: 7d1e5b9c3a20
Revises: 2c4a62de73e3
Create Date: 2026-10-06 12:00:00

The AI assistant was removed. Databases made before that still have its two tables and the
pgvector extension; a new database never had them (the initial migration no longer creates
them), so every statement here is "IF EXISTS".
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '7d1e5b9c3a20'
down_revision = '2c4a62de73e3'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS chat_messages")
    op.execute("DROP TABLE IF EXISTS kb_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")


def downgrade():
    # The assistant is gone, so there is nothing to bring back.
    pass
