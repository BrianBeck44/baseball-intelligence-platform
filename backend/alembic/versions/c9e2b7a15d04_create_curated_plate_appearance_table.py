"""create curated plate appearance table

Revision ID: c9e2b7a15d04
Revises: f1a9c3e84b06
Create Date: 2026-09-26 08:44:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9e2b7a15d04"
down_revision: Union[str, Sequence[str], None] = "f1a9c3e84b06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.plate_appearance."""
    op.create_table(
        "plate_appearance",
        sa.Column(
            "plate_appearance_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("at_bat_number", sa.Integer(), nullable=False),
        sa.Column("batter_id", sa.BigInteger(), nullable=False),
        sa.Column("pitcher_id", sa.BigInteger(), nullable=False),
        sa.Column("batter_team_id", sa.BigInteger(), nullable=False),
        sa.Column("pitcher_team_id", sa.BigInteger(), nullable=False),
        sa.Column("inning", sa.SmallInteger(), nullable=False),
        sa.Column("inning_topbot", sa.String(3), nullable=False),
        sa.Column("outcome_type_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("plate_appearance_id", name="pk_plate_appearance"),
        sa.UniqueConstraint(
            "game_id",
            "at_bat_number",
            name="uq_plate_appearance_game_at_bat",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["curated.game.game_id"],
            name="fk_plate_appearance_game",
        ),
        sa.ForeignKeyConstraint(
            ["batter_id"],
            ["curated.player.player_id"],
            name="fk_plate_appearance_batter",
        ),
        sa.ForeignKeyConstraint(
            ["pitcher_id"],
            ["curated.player.player_id"],
            name="fk_plate_appearance_pitcher",
        ),
        sa.ForeignKeyConstraint(
            ["batter_team_id"],
            ["curated.team.team_id"],
            name="fk_plate_appearance_batter_team",
        ),
        sa.ForeignKeyConstraint(
            ["pitcher_team_id"],
            ["curated.team.team_id"],
            name="fk_plate_appearance_pitcher_team",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_type_id"],
            ["curated.outcome_type.id"],
            name="fk_plate_appearance_outcome_type",
        ),
        sa.CheckConstraint(
            "inning_topbot IN ('Top', 'Bot')",
            name="ck_plate_appearance_inning_topbot",
        ),
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.plate_appearance."""
    op.drop_table("plate_appearance", schema="curated")
