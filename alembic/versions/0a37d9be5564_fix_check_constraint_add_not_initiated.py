"""fix_check_constraint_add_not_initiated

Revision ID: 0a37d9be5564
Revises: 01ace21bc136
Create Date: 2026-07-18 15:28:19.707653

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a37d9be5564'
down_revision: Union[str, Sequence[str], None] = '01ace21bc136'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Manually drop the old CHECK constraint and add the new one."""
    # Drop old constraint that excludes 'not_initiated'
    op.drop_constraint(
        "check_verification_status",   # exact name from pgAdmin
        "provider_profiles",
        type_="check"
    )
    # Re-create with not_initiated included
    op.create_check_constraint(
        "check_verification_status",
        "provider_profiles",
        "verification_status IN ('not_initiated', 'pending', 'approved', 'rejected')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "check_verification_status",
        "provider_profiles",
        type_="check"
    )
    op.create_check_constraint(
        "check_verification_status",
        "provider_profiles",
        "verification_status IN ('pending', 'approved', 'rejected')"
    )
