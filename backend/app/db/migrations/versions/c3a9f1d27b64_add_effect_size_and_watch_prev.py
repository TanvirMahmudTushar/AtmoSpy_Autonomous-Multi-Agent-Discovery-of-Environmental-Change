"""add effect_size to findings and prev_* snapshot to watches

Revision ID: c3a9f1d27b64
Revises: 22d18092431f
Create Date: 2026-09-30 12:00:00.000000

"""
import statistics
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a9f1d27b64'
down_revision: Union[str, None] = '22d18092431f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('findings', sa.Column('effect_size', sa.Float(), nullable=True))
    op.add_column('watches', sa.Column('prev_trend_per_year', sa.Float(), nullable=True))
    op.add_column('watches', sa.Column('prev_significance', sa.String(length=32), nullable=True))

    # Backfill existing findings from their stored annual series, using the
    # same formula report_agent applies to new ones: |total_change| / sample
    # std. dev. (ddof=1, matching analysis/trend.py).
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT f.id AS id, f.total_change AS total_change, v.data AS data "
            "FROM findings f JOIN visualizations v "
            "ON v.finding_id = f.id AND v.kind = 'timeseries'"
        )
    ).mappings().all()
    for row in rows:
        values = [p["value"] for p in (row["data"] or {}).get("points", []) if p.get("value") is not None]
        if len(values) < 2:
            continue
        std = statistics.stdev(values)
        effect = 0.0 if std == 0 else abs(row["total_change"]) / std
        bind.execute(
            sa.text("UPDATE findings SET effect_size = :e WHERE id = :id"),
            {"e": effect, "id": row["id"]},
        )


def downgrade() -> None:
    op.drop_column('watches', 'prev_significance')
    op.drop_column('watches', 'prev_trend_per_year')
    op.drop_column('findings', 'effect_size')
