"""stats v2: analysis version, temporal basis, trend details, detectability,
seasonal trends on findings; statistical_method becomes Text

Existing rows are analysis_version 1 (annual means, uncorrected
Mann-Kendall); new findings are written as version 2 (monthly anomalies,
autocorrelation-corrected tests). The new JSONB columns stay NULL for v1.

Revision ID: f1a2c3d4e5b6
Revises: e5b7d0a94c18
Create Date: 2026-10-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f1a2c3d4e5b6'
down_revision: Union[str, None] = 'e5b7d0a94c18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('findings', sa.Column('analysis_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('findings', sa.Column('temporal_basis', sa.String(length=24), nullable=False, server_default='annual'))
    op.add_column('findings', sa.Column('trend_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('findings', sa.Column('detectability', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('findings', sa.Column('seasonal_trends', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.alter_column('findings', 'statistical_method', type_=sa.Text(), existing_type=sa.String(length=128))
    op.add_column('watches', sa.Column('last_analysis_version', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('watches', 'last_analysis_version')
    op.alter_column('findings', 'statistical_method', type_=sa.String(length=128), existing_type=sa.Text())
    op.drop_column('findings', 'seasonal_trends')
    op.drop_column('findings', 'detectability')
    op.drop_column('findings', 'trend_details')
    op.drop_column('findings', 'temporal_basis')
    op.drop_column('findings', 'analysis_version')
