"""create initial database schemas

Revision ID: 0268718699c2
Revises: 
Create Date: 2026-09-11 14:56:03.530379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0268718699c2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial PostgreSQL schemas."""
    op.execute(sa.schema.CreateSchema("raw"))
    op.execute(sa.schema.CreateSchema("staging"))
    op.execute(sa.schema.CreateSchema("curated"))
    op.execute(sa.schema.CreateSchema("analytics"))


def downgrade() -> None:
    """Drop the initial PostgreSQL schemas in reverse order."""
    op.execute(sa.schema.DropSchema("analytics"))
    op.execute(sa.schema.DropSchema("curated"))
    op.execute(sa.schema.DropSchema("staging"))
    op.execute(sa.schema.DropSchema("raw"))

