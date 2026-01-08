"""
Initial Database Setup Script for MySQL

This script will:
- Connect to MySQL server using credentials from config.config.DATABASE
- Create the database if it does not exist
- Execute the SQL in database/init_database.sql (idempotent)
- Optionally run programmatic migration adjustments to align with current code

Usage (PowerShell):
  python database/init_database.py

Note: Requires MySQL running and a user with privileges to create database/tables.
"""

from pathlib import Path
import os
import sys
import pymysql

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.config import DATABASE  # type: ignore
from utils.logger import bot_logger  # type: ignore


SQL_FILE = ROOT / "database" / "init_database.sql"


def _connect_without_db():
    """Connect to MySQL server without selecting a database."""
    return pymysql.connect(
        host=DATABASE['host'],
        user=DATABASE['user'],
        password=DATABASE['password'],
        port=DATABASE['port'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _split_sql_statements(sql_text: str):
    """A very simple splitter for SQL statements by semicolon.
    Assumes the SQL file doesn't contain procedures/triggers with custom delimiters.
    Filters out comments and empty statements.
    """
    lines = []
    for line in sql_text.splitlines():
        striped = line.strip()
        if not striped:
            continue
        if striped.startswith('--'):
            continue
        lines.append(line)
    cleaned = '\n'.join(lines)
    parts = [p.strip() for p in cleaned.split(';')]
    return [p for p in parts if p]


def create_database_if_missing():
    dbname = DATABASE['database']
    with _connect_without_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE DATABASE IF NOT EXISTS `{}`
                DEFAULT CHARACTER SET utf8mb4
                COLLATE utf8mb4_unicode_ci
            """.format(dbname))
            bot_logger.info(f"✅ Database '{dbname}' ensured (created if missing)")


def execute_sql_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")

    sql_text = path.read_text(encoding='utf-8')
    statements = _split_sql_statements(sql_text)

    with _connect_without_db() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    # Log statement causing error for easier debugging
                    bot_logger.error(f"❌ SQL error: {e}\nStatement: {stmt[:500]}...")
                    raise
    bot_logger.info(f"✅ Executed {len(statements)} SQL statements from {path.name}")


def main():
    bot_logger.info("=" * 60)
    bot_logger.info("🚀 Starting initial database setup")
    bot_logger.info("=" * 60)

    try:
        create_database_if_missing()
        execute_sql_file(SQL_FILE)

        bot_logger.info("\n" + "=" * 60)
        bot_logger.info("🎉 Initial database setup completed successfully")
        bot_logger.info("=" * 60)

        print("\nNext steps:")
        print("  • Run the migration verifier (optional): python database/migrate_database.py")
        print("  • Start the app: python run.py")

    except Exception as e:
        bot_logger.error(f"❌ Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
