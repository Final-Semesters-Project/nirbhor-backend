"""booking unique initiated index and provider geography index

Revision ID: 241671b4ffe3
Revises: 48ef5780e39b
Create Date: 2026-11-22 17:11:33.373598

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '241671b4ffe3'
down_revision: Union[str, Sequence[str], None] = '48ef5780e39b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Keep only the newest initiated booking per seeker so the unique index can be created
    op.execute("""
        UPDATE bookings SET status = 'auto_expired'
        WHERE status = 'initiated' AND id NOT IN (
            SELECT DISTINCT ON (seeker_id) id FROM bookings
            WHERE status = 'initiated' ORDER BY seeker_id, created_at DESC
        )
    """)
    # 2. Enforce at most one open ('initiated') booking per seeker at the DB level
    op.create_index(
        "uq_one_initiated_per_seeker",
        "bookings",
        ["seeker_id"],
        unique=True,
        postgresql_where=sa.text("status = 'initiated'"),
    )
    # 3. Spatial GiST index on geography cast for fast ST_DWithin search queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_provider_profiles_base_location_geog "
        "ON provider_profiles USING gist ((base_location::geography))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_provider_profiles_base_location_geog")
    op.drop_index("uq_one_initiated_per_seeker", table_name="bookings")
