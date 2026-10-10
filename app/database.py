"""SQLite connection management and inventory schema setup."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

DATABASE_FILE = Path(__file__).resolve().parent.parent / "inventory.db"


@contextmanager
def database_connection(
    database_file: Path = DATABASE_FILE,
) -> Generator[sqlite3.Connection, None, None]:
    """Open a SQLite connection with foreign keys and transaction handling."""

    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_file: Path = DATABASE_FILE) -> None:
    """Create the category, product, and stock movement tables."""

    with database_connection(database_file) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                description TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sku TEXT NOT NULL COLLATE NOCASE UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                category_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                reorder_level INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL CHECK (movement_type IN ('receive', 'issue')),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_products_category_id
                ON products(category_id);
            CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id
                ON stock_movements(product_id);
            """
        )
