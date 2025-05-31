"""Initial migration

Revision ID: 9d97c6fac45e
Revises: 9c6cf356508b
Create Date: 2025-05-02 14:58:52.377765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d97c6fac45e'
down_revision: Union[str, None] = '9c6cf356508b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
