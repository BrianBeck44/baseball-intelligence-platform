"""add stand and p_throws to plate appearance

Revision ID: d8a1c4f27b90
Revises: c9e2b7a15d04
Create Date: 2026-09-28 12:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8a1c4f27b90"
down_revision: Union[str, Sequence[str], None] = "c9e2b7a15d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add batter stance and pitcher throwing hand to curated.plate_appearance."""
    op.add_column(
        "plate_appearance",
        sa.Column("stand", sa.String(1), nullable=True),
        schema="curated",
    )
    op.add_column(
        "plate_appearance",
        sa.Column("p_throws", sa.String(1), nullable=True),
        schema="curated",
    )

    # Existing rows (if any) cannot receive NOT NULL columns without values.
    # Backfill from the Statcast pitch that produced each plate appearance.
    op.execute(
        """
        UPDATE curated.plate_appearance AS pa
        SET
            stand = src.stand,
            p_throws = src.p_throws
        FROM (
            SELECT DISTINCT ON (g.game_id, sp.at_bat_number)
                g.game_id,
                sp.at_bat_number,
                sp.stand,
                sp.p_throws
            FROM raw.statcast_pitch AS sp
            JOIN curated.game AS g
              ON g.mlb_game_pk = sp.game_pk
            WHERE sp.stand IN ('L', 'R', 'S')
              AND sp.p_throws IN ('L', 'R')
            ORDER BY g.game_id, sp.at_bat_number, sp.pitch_number DESC
        ) AS src
        WHERE pa.game_id = src.game_id
          AND pa.at_bat_number = src.at_bat_number
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM curated.plate_appearance
                WHERE stand IS NULL
                    OR p_throws IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Unable to backfill stand/p_throws for all curated.plate_appearance rows';
            END IF;
        END $$;
        """
    )

    op.alter_column(
        "plate_appearance",
        "stand",
        existing_type=sa.String(1),
        nullable=False,
        schema="curated",
    )
    op.alter_column(
        "plate_appearance",
        "p_throws",
        existing_type=sa.String(1),
        nullable=False,
        schema="curated",
    )
    op.create_check_constraint(
        "ck_plate_appearance_stand",
        "plate_appearance",
        "stand IN ('L', 'R', 'S')",
        schema="curated",
    )
    op.create_check_constraint(
        "ck_plate_appearance_p_throws",
        "plate_appearance",
        "p_throws IN ('L', 'R')",
        schema="curated",
    )


def downgrade() -> None:
    """Remove batter stance and pitcher throwing hand from curated.plate_appearance."""
    op.drop_constraint(
        "ck_plate_appearance_stand",
        "plate_appearance",
        schema="curated",
        type_="check",
    )
    op.drop_constraint(
        "ck_plate_appearance_p_throws",
        "plate_appearance",
        schema="curated",
        type_="check",
    )
    op.drop_column("plate_appearance", "stand", schema="curated")
    op.drop_column("plate_appearance", "p_throws", schema="curated")
