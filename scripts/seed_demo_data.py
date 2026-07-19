#!/usr/bin/env python3
"""
Creates a small demo SQLite database (customers/orders/products) so you can
try AI SQL Copilot immediately without hooking up a real database.

Reads its schema and data from datasets/demo/schema.sql and
datasets/demo/seed_data.sql - edit those plain SQL files to customize the
demo data without touching this script.

Usage:
    python3 scripts/seed_demo_data.py [output_path]

Then in the app, add a connection with engine=sqlite and this file's path.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DEFAULT_OUTPUT = "demo.sqlite"
DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets" / "demo"


def main() -> None:
    output_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT)
    if output_path.exists():
        print(f"{output_path} already exists - delete it first if you want to re-seed.")
        return

    schema_sql = (DATASETS_DIR / "schema.sql").read_text()
    seed_sql = (DATASETS_DIR / "seed_data.sql").read_text()

    conn = sqlite3.connect(output_path)
    conn.executescript(schema_sql)
    conn.executescript(seed_sql)
    conn.commit()
    conn.close()

    print(f"Created demo database at {output_path.resolve()}")
    print(f"(schema/data loaded from {DATASETS_DIR.relative_to(Path(__file__).resolve().parent.parent)})")
    print("Add a connection in the app with engine=sqlite and this file path.")


if __name__ == "__main__":
    main()
