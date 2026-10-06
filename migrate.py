#!/usr/bin/env python3
"""
CLI entry point to execute pending database migrations.
Usage:
    python migrate.py
"""
import asyncio
import sys
from src.migrations.runner import run_all_migrations


def main():
    try:
        asyncio.run(run_all_migrations())
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
