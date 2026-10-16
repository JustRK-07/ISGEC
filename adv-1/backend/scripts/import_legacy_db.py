"""One-shot migration: copy rows from ../data/adv.db (Node SQLite) into the new
FastAPI SQLite schema.

Run from adv/backend/:

    python scripts/import_legacy_db.py

The legacy schema lives in lib/db.js (../). Column names are identical
(snake_case), so this is a straight row copy.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

LEGACY_DB = Path(__file__).resolve().parent.parent.parent.parent / "data" / "adv.db"
TARGET_DB = Path(__file__).resolve().parent.parent / "data" / "adv.db"


def main() -> int:
    if not LEGACY_DB.exists():
        print(f"Legacy DB not found at {LEGACY_DB}. Nothing to migrate.")
        return 1

    TARGET_DB.parent.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(str(LEGACY_DB))
    src.row_factory = sqlite3.Row

    dst = sqlite3.connect(str(TARGET_DB))
    dst.row_factory = sqlite3.Row

    # Ensure the target schema exists. Importing the ORM models triggers
    # SQLAlchemy's metadata.create_all().
    from app.db import init_db

    init_db()

    tables = ["projects", "files", "entities", "issues"]
    for table in tables:
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table}: 0 rows")
            continue
        cols = rows[0].keys()
        placeholders = ", ".join(["?"] * len(cols))
        col_list = ", ".join(cols)
        for row in rows:
            dst.execute(
                f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
                tuple(row[c] for c in cols),
            )
        print(f"  {table}: copied {len(rows)} rows")

    dst.commit()
    dst.close()
    src.close()
    print(f"\n✓ Migrated legacy DB → {TARGET_DB}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
