"""Inventory operations and their SQLite persistence."""

import sqlite3
from pathlib import Path

from app.database import DATABASE_FILE, database_connection
from app.models import (
    CategoryInput,
    ProductCreate,
    ProductInput,
    StockMovementInput,
)


class NotFoundError(LookupError):
    """Raised when an inventory record does not exist."""


class ConflictError(Exception):
    """Raised when an operation conflicts with inventory data or stock rules."""


class InventoryService:
    """Coordinate category, product, and stock movement operations."""

    def __init__(self, database_file: Path = DATABASE_FILE) -> None:
        self.database_file = database_file

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, object] | None:
        return dict(row) if row is not None else None

    @classmethod
    def _required_row(
        cls, row: sqlite3.Row | None, message: str
    ) -> dict[str, object]:
        result = cls._row_to_dict(row)
        if result is None:
            raise NotFoundError(message)
        return result

    @staticmethod
    def _insert_movement(
        connection: sqlite3.Connection,
        product_id: int,
        movement_type: str,
        quantity: int,
        note: str,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO stock_movements (product_id, movement_type, quantity, note)
            VALUES (?, ?, ?, ?)
            """,
            (product_id, movement_type, quantity, note),
        )
        return cursor.lastrowid

    def list_categories(self) -> list[dict[str, object]]:
        with database_connection(self.database_file) as connection:
            rows = connection.execute(
                "SELECT id, name, description FROM categories ORDER BY name"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_category(self, category_id: int) -> dict[str, object]:
        with database_connection(self.database_file) as connection:
            row = connection.execute(
                "SELECT id, name, description FROM categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        return self._required_row(row, "Category not found.")

    def create_category(self, category: CategoryInput) -> dict[str, object]:
        try:
            with database_connection(self.database_file) as connection:
                cursor = connection.execute(
                    "INSERT INTO categories (name, description) VALUES (?, ?)",
                    (category.name, category.description),
                )
                row = connection.execute(
                    "SELECT id, name, description FROM categories WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ConflictError("A category with this name already exists.") from error
        return self._required_row(row, "Category could not be created.")

    def update_category(
        self, category_id: int, category: CategoryInput
    ) -> dict[str, object]:
        try:
            with database_connection(self.database_file) as connection:
                cursor = connection.execute(
                    "UPDATE categories SET name = ?, description = ? WHERE id = ?",
                    (category.name, category.description, category_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Category not found.")
                row = connection.execute(
                    "SELECT id, name, description FROM categories WHERE id = ?",
                    (category_id,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ConflictError("A category with this name already exists.") from error
        return self._required_row(row, "Category not found.")

    def delete_category(self, category_id: int) -> None:
        try:
            with database_connection(self.database_file) as connection:
                cursor = connection.execute(
                    "DELETE FROM categories WHERE id = ?", (category_id,)
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Category not found.")
        except sqlite3.IntegrityError as error:
            raise ConflictError(
                "Cannot delete a category while it contains products."
            ) from error

    def list_products(
        self, query: str | None = None, category_id: int | None = None
    ) -> list[dict[str, object]]:
        conditions: list[str] = []
        parameters: list[object] = []
        if query and query.strip():
            conditions.append("(p.name LIKE ? OR p.sku LIKE ? OR p.description LIKE ?)")
            search = f"%{query.strip()}%"
            parameters.extend((search, search, search))
        if category_id is not None:
            conditions.append("p.category_id = ?")
            parameters.append(category_id)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with database_connection(self.database_file) as connection:
            rows = connection.execute(
                f"""
                SELECT p.id, p.name, p.sku, p.description, p.category_id,
                       p.quantity, p.reorder_level, p.created_at, p.updated_at
                FROM products AS p
                {where_clause}
                ORDER BY p.name, p.id
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_low_stock_products(self) -> list[dict[str, object]]:
        with database_connection(self.database_file) as connection:
            rows = connection.execute(
                """
                SELECT id, name, sku, description, category_id, quantity,
                       reorder_level, created_at, updated_at
                FROM products
                WHERE quantity <= reorder_level
                ORDER BY quantity, name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_product(self, product_id: int) -> dict[str, object]:
        with database_connection(self.database_file) as connection:
            row = connection.execute(
                """
                SELECT id, name, sku, description, category_id, quantity,
                       reorder_level, created_at, updated_at
                FROM products WHERE id = ?
                """,
                (product_id,),
            ).fetchone()
        return self._required_row(row, "Product not found.")

    def create_product(self, product: ProductCreate) -> dict[str, object]:
        try:
            with database_connection(self.database_file) as connection:
                category = connection.execute(
                    "SELECT id FROM categories WHERE id = ?",
                    (product.category_id,),
                ).fetchone()
                if category is None:
                    raise NotFoundError("Category not found.")
                cursor = connection.execute(
                    """
                    INSERT INTO products
                        (name, sku, description, category_id, quantity, reorder_level)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product.name,
                        product.sku,
                        product.description,
                        product.category_id,
                        product.initial_quantity,
                        product.reorder_level,
                    ),
                )
                product_id = cursor.lastrowid
                if product.initial_quantity:
                    self._insert_movement(
                        connection,
                        product_id,
                        "receive",
                        product.initial_quantity,
                        "Initial stock",
                    )
                row = connection.execute(
                    """
                    SELECT id, name, sku, description, category_id, quantity,
                           reorder_level, created_at, updated_at
                    FROM products WHERE id = ?
                    """,
                    (product_id,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ConflictError("A product with this SKU already exists.") from error
        return self._required_row(row, "Product could not be created.")

    def update_product(
        self, product_id: int, product: ProductInput
    ) -> dict[str, object]:
        try:
            with database_connection(self.database_file) as connection:
                existing = connection.execute(
                    "SELECT id FROM products WHERE id = ?", (product_id,)
                ).fetchone()
                if existing is None:
                    raise NotFoundError("Product not found.")
                category = connection.execute(
                    "SELECT id FROM categories WHERE id = ?",
                    (product.category_id,),
                ).fetchone()
                if category is None:
                    raise NotFoundError("Category not found.")
                connection.execute(
                    """
                    UPDATE products
                    SET name = ?, sku = ?, description = ?, category_id = ?,
                        reorder_level = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        product.name,
                        product.sku,
                        product.description,
                        product.category_id,
                        product.reorder_level,
                        product_id,
                    ),
                )
                row = connection.execute(
                    """
                    SELECT id, name, sku, description, category_id, quantity,
                           reorder_level, created_at, updated_at
                    FROM products WHERE id = ?
                    """,
                    (product_id,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ConflictError("A product with this SKU already exists.") from error
        return self._required_row(row, "Product not found.")

    def delete_product(self, product_id: int) -> None:
        try:
            with database_connection(self.database_file) as connection:
                cursor = connection.execute(
                    "DELETE FROM products WHERE id = ?", (product_id,)
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Product not found.")
        except sqlite3.IntegrityError as error:
            raise ConflictError(
                "Cannot delete a product that has stock movement history."
            ) from error

    def record_stock_movement(
        self, product_id: int, movement: StockMovementInput
    ) -> dict[str, object]:
        with database_connection(self.database_file) as connection:
            connection.execute("BEGIN IMMEDIATE")
            product = connection.execute(
                "SELECT quantity FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if product is None:
                raise NotFoundError("Product not found.")

            if movement.movement_type == "receive":
                connection.execute(
                    """
                    UPDATE products
                    SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (movement.quantity, product_id),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE products
                    SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND quantity >= ?
                    """,
                    (movement.quantity, product_id, movement.quantity),
                )
                if cursor.rowcount == 0:
                    raise ConflictError("Insufficient stock to issue this quantity.")

            movement_id = self._insert_movement(
                connection,
                product_id,
                movement.movement_type,
                movement.quantity,
                movement.note,
            )
            row = connection.execute(
                """
                SELECT id, product_id, movement_type, quantity, note, created_at
                FROM stock_movements WHERE id = ?
                """,
                (movement_id,),
            ).fetchone()
        return self._required_row(row, "Stock movement could not be recorded.")

    def list_stock_movements(
        self, product_id: int | None = None
    ) -> list[dict[str, object]]:
        with database_connection(self.database_file) as connection:
            if product_id is None:
                rows = connection.execute(
                    """
                    SELECT id, product_id, movement_type, quantity, note, created_at
                    FROM stock_movements ORDER BY id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, product_id, movement_type, quantity, note, created_at
                    FROM stock_movements WHERE product_id = ? ORDER BY id DESC
                    """,
                    (product_id,),
                ).fetchall()
        return [dict(row) for row in rows]
