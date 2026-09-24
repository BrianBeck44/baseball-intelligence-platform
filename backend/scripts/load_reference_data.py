"""CLI adapter for loading curated reference data."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine

from app.core.config import settings
from app.curated.reference_data import load_reference_data


def main() -> int:
    engine = create_engine(settings.database_url)

    try:
        with engine.begin() as connection:
            load_reference_data(connection)
    finally:
        engine.dispose()

    print("Curated reference data loaded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())