"""enable row level security on app tables

Supabase exposes every table in the `public` schema through its auto-generated
REST API, reachable with the project's public anon key. This app never uses
that API — the FastAPI backend is the only client, connecting as the table
owner — so turning RLS on with no policies closes that door (users.password_hash
included) without changing anything the backend can do: table owners bypass RLS.

On plain Postgres (docker-compose, CI) the app role is also the owner, so this
is behaviourally a no-op there.

Revision ID: e5b7d0a94c18
Revises: c3a9f1d27b64
Create Date: 2026-09-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5b7d0a94c18'
down_revision: Union[str, None] = 'c3a9f1d27b64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Listed explicitly rather than discovered: PostGIS's own `spatial_ref_sys`
# also lives in `public` and is owned by a different role on hosted Postgres,
# so a blanket "every table" loop would fail there.
APP_TABLES = (
    'users',
    'datasets',
    'variables',
    'regions',
    'investigations',
    'investigation_steps',
    'observations',
    'analysis_results',
    'findings',
    'visualizations',
    'reports',
    'provenance',
    'nasa_query_cache',
    'watches',
)


def upgrade() -> None:
    for table in APP_TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in APP_TABLES:
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
