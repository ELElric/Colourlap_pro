"""Initialize the database for a project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from colorlab_pro.database.session import create_engine_from_path, init_schema  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize ColorLab Pro SQLite database")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=ROOT / "data" / "user" / "default" / "colorlab.db",
        help="Path to the SQLite database file",
    )
    args = parser.parse_args()

    engine = create_engine_from_path(args.db_path)
    init_schema(engine)
    print(f"Initialized database: {args.db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
