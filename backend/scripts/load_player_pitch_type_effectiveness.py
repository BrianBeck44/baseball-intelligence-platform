"""Replace analytics.player_pitch_type_effectiveness from curated pitches."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_pitch_type_effectiveness_loader import (
    load_player_pitch_type_effectiveness_from_curated,
)
from app.analytics.rebuild_validation import (
    validate_player_pitch_type_effectiveness_load,
)
from app.core.config import settings


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            text("DELETE FROM analytics.player_pitch_type_effectiveness")
        )
        result = load_player_pitch_type_effectiveness_from_curated(connection)
        validate_player_pitch_type_effectiveness_load(connection, result)
        transaction.commit()
        print("Pitch type effectiveness load complete.")
        print(f"Extracted: {result.extracted_count}")
        print(f"Transformed: {result.transformed_count}")
        print(f"Loaded: {result.loaded_count}")
        print("aggregate validation: succeeded")
        print("commit: succeeded")
        return 0
    except Exception as exc:
        transaction.rollback()
        print(f"player_pitch_type_effectiveness load failed: {exc}")
        raise
    finally:
        connection.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
