"""remove pro bono and CA quotes

Revision ID: 3b8f6c2d9e41
Revises: 7d1e5b9c3a20
Create Date: 2026-10-07 12:00:00

Pro bono and CA quotes were removed: a CA accepts a request at their listed prices or
declines it. Engagements that were quoted or pro bono are deleted with the rows that point
at them; a filing such an engagement had "With CA" goes back to upcoming (or overdue).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3b8f6c2d9e41'
down_revision = '7d1e5b9c3a20'
branch_labels = None
depends_on = None

GONE = "SELECT id FROM engagements WHERE status = 'quoted' OR is_pro_bono"


def upgrade():
    # Filings that a deleted engagement had "With CA" are not started again.
    op.execute(f"""
        UPDATE compliance_items
        SET status = CASE WHEN due_date < CURRENT_DATE THEN 'overdue' ELSE 'upcoming' END
        WHERE status = 'with_ca' AND id IN (
            SELECT compliance_item_id FROM engagement_items WHERE engagement_id IN ({GONE})
        )
    """)
    op.drop_table('pro_bono_requests')
    for table in ('document_requests', 'ratings', 'engagement_items'):
        op.execute(f"DELETE FROM {table} WHERE engagement_id IN ({GONE})")
    op.execute(f"DELETE FROM engagements WHERE id IN ({GONE})")

    op.drop_constraint(op.f('ck_engagements_quote_needs_reason'), 'engagements', type_='check')
    op.drop_column('engagements', 'quote_reason')
    op.drop_column('engagements', 'is_pro_bono')
    op.drop_constraint(
        op.f('ck_engagement_items_quoted_price_not_negative'), 'engagement_items', type_='check'
    )
    op.drop_column('engagement_items', 'quoted_price')
    op.drop_constraint(
        op.f('ck_ca_profiles_pro_bono_slots_not_negative'), 'ca_profiles', type_='check'
    )
    op.drop_column('ca_profiles', 'pro_bono_slots_per_month')


def downgrade():
    # The columns and the table come back empty; the deleted engagements do not.
    op.add_column(
        'ca_profiles',
        sa.Column('pro_bono_slots_per_month', sa.Integer(), server_default='0', nullable=False),
    )
    op.create_check_constraint(
        op.f('ck_ca_profiles_pro_bono_slots_not_negative'),
        'ca_profiles',
        'pro_bono_slots_per_month >= 0',
    )
    op.add_column('engagement_items', sa.Column('quoted_price', sa.Numeric(12, 2), nullable=True))
    op.add_column(
        'engagements',
        sa.Column('is_pro_bono', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column('engagements', sa.Column('quote_reason', sa.String(length=1000), nullable=True))
    op.create_check_constraint(
        op.f('ck_engagements_quote_needs_reason'),
        'engagements',
        "status <> 'quoted' OR quote_reason IS NOT NULL",
    )
    op.create_check_constraint(
        op.f('ck_engagement_items_quoted_price_not_negative'),
        'engagement_items',
        'quoted_price IS NULL OR quoted_price >= 0',
    )
    op.create_table(
        'pro_bono_requests',
        sa.Column('business_id', sa.Uuid(), sa.ForeignKey('businesses.id'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('note', sa.String(length=1000), server_default='', nullable=False),
        sa.Column('compliance_item_ids', sa.ARRAY(sa.Uuid()), server_default='{}', nullable=False),
        sa.Column('engagement_id', sa.Uuid(), sa.ForeignKey('engagements.id'), unique=True),
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
