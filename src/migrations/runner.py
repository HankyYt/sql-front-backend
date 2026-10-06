import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg

from config import settings

logger = logging.getLogger("migrations")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] [migrations] %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Path to migrations directory in the project root
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def to_asyncpg_dsn(url: str, db_name: str | None = None) -> str:
    """Normalize SQLAlchemy or PostgreSQL URL to asyncpg DSN and optionally swap database name."""
    clean_url = re.sub(r"^postgresql\+[a-zA-Z0-9_]+:", "postgresql:", url)
    if db_name:
        parsed = urlparse(clean_url)
        clean_url = urlunparse(parsed._replace(path=f"/{db_name}"))
    return clean_url


async def connect_with_retry(dsn: str, max_retries: int = 5, delay: float = 2.0) -> asyncpg.Connection:
    """Attempt connecting to the database with retry logic."""
    for attempt in range(1, max_retries + 1):
        try:
            return await asyncpg.connect(dsn, timeout=10)
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
            logger.warning(
                f"Connection attempt {attempt}/{max_retries} failed ({e}). Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)


async def apply_migrations_for_db(db_name: str, migrations_dir: Path):
    """Apply all unapplied SQL migration files for a given database."""
    if not migrations_dir.exists():
        return

    sql_files = sorted([f for f in migrations_dir.glob("*.sql") if f.is_file()])
    if not sql_files:
        logger.info(f"[{db_name}] No migration files found in {migrations_dir.name}/.")
        return

    # Use DATABASE_URL credentials (superuser) to apply migrations across databases
    dsn = to_asyncpg_dsn(settings.DATABASE_URL, db_name=db_name)
    logger.info(f"[{db_name}] Checking migrations in {migrations_dir}...")

    conn = await connect_with_retry(dsn)
    try:
        # 1. Ensure schema_migrations table exists
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                version VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        # 2. Get already applied versions
        rows = await conn.fetch("SELECT version FROM schema_migrations;")
        applied = {row["version"] for row in rows}

        # 3. Apply pending migrations sequentially
        applied_count = 0
        for sql_file in sql_files:
            version = sql_file.name
            if version in applied:
                continue

            logger.info(f"[{db_name}] Applying migration: {version}...")
            content = sql_file.read_text(encoding="utf-8")

            async with conn.transaction():
                await conn.execute(content)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1);",
                    version,
                )

            logger.info(f"[{db_name}] Successfully applied: {version}")
            applied_count += 1

        if applied_count == 0:
            logger.info(f"[{db_name}] Database is already up to date ({len(applied)} migrations applied).")
        else:
            logger.info(f"[{db_name}] Applied {applied_count} new migration(s).")
    finally:
        await conn.close()


async def run_all_migrations():
    """Scan and apply migrations for all known databases."""
    logger.info(f"Starting database migration runner (base dir: {MIGRATIONS_DIR})...")
    databases = ["users_db", "game_db", "quest_db"]
    for db_name in databases:
        db_migrations = MIGRATIONS_DIR / db_name
        if db_migrations.exists():
            try:
                await apply_migrations_for_db(db_name, db_migrations)
            except Exception as e:
                logger.error(f"Error migrating {db_name}: {e}", exc_info=True)
                raise
    logger.info("All database migrations completed successfully.")
