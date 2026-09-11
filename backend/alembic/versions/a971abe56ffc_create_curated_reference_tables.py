"""create curated reference tables

Revision ID: a971abe56ffc
Revises: 0268718699c2
Create Date: 2026-09-11 17:34:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a971abe56ffc"
down_revision: Union[str, Sequence[str], None] = "0268718699c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated reference tables."""
    op.create_table(
        "league",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_league"),
        sa.UniqueConstraint("code", name="uq_league_code"),
        schema="curated",
    )

    op.create_table(
        "division",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_division"),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["curated.league.id"],
            name="fk_division_league",
        ),
        sa.UniqueConstraint(
            "league_id",
            "code",
            name="uq_division_league_id_code",
        ),
        schema="curated",
    )

    op.create_table(
        "game_type",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_game_type"),
        sa.UniqueConstraint("code", name="uq_game_type_code"),
        schema="curated",
    )

    op.create_table(
        "position_type",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_position_type"),
        sa.UniqueConstraint("code", name="uq_position_type_code"),
        schema="curated",
    )

    op.create_table(
        "pitch_type",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_pitch_type"),
        sa.UniqueConstraint("code", name="uq_pitch_type_code"),
        schema="curated",
    )

    op.create_table(
        "outcome_type",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_outcome_type"),
        sa.UniqueConstraint("code", name="uq_outcome_type_code"),
        schema="curated",
    )

    op.create_table(
        "pitch_outcome_type",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_pitch_outcome_type"),
        sa.UniqueConstraint("code", name="uq_pitch_outcome_type_code"),
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated reference tables in dependency-safe order."""
    op.drop_table("pitch_outcome_type", schema="curated")
    op.drop_table("outcome_type", schema="curated")
    op.drop_table("pitch_type", schema="curated")
    op.drop_table("position_type", schema="curated")
    op.drop_table("game_type", schema="curated")
    op.drop_table("division", schema="curated")
    op.drop_table("league", schema="curated")
