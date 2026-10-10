"""Tests for stockroom inventory operations."""

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.database import initialize_database
from app.models import (
    CategoryInput,
    ProductCreate,
    ProductInput,
    StockMovementInput,
)
from app.services import ConflictError, InventoryService, NotFoundError


class InventoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_file = Path(self.temporary_directory.name) / "inventory.db"
        initialize_database(self.database_file)
        self.inventory = InventoryService(self.database_file)

    def create_category(self, name: str = "Office supplies") -> dict[str, object]:
        return self.inventory.create_category(
            CategoryInput(name=name, description="Supplies for staff")
        )

    def create_product(
        self, category_id: int, initial_quantity: int = 0
    ) -> dict[str, object]:
        return self.inventory.create_product(
            ProductCreate(
                name="A4 copy paper",
                sku="PAPER-A4",
                category_id=category_id,
                reorder_level=3,
                initial_quantity=initial_quantity,
            )
        )

    def test_category_and_product_crud_and_search(self) -> None:
        category = self.create_category()
        product = self.create_product(int(category["id"]), initial_quantity=5)

        self.assertEqual(self.inventory.get_category(int(category["id"])), category)
        self.assertEqual(self.inventory.get_product(int(product["id"])), product)
        self.assertEqual(
            [item["id"] for item in self.inventory.list_products(query="paper")],
            [product["id"]],
        )
        self.assertEqual(
            [item["id"] for item in self.inventory.list_low_stock_products()], []
        )

        updated = self.inventory.update_product(
            int(product["id"]),
            ProductInput(
                name="Recycled A4 paper",
                sku="PAPER-A4",
                category_id=int(category["id"]),
                reorder_level=6,
            ),
        )
        self.assertEqual(updated["quantity"], 5)
        self.assertEqual(len(self.inventory.list_low_stock_products()), 1)

        with self.assertRaises(ConflictError):
            self.inventory.delete_category(int(category["id"]))

    def test_stock_movements_are_atomic_and_preserve_history(self) -> None:
        category = self.create_category()
        product = self.create_product(int(category["id"]), initial_quantity=5)
        product_id = int(product["id"])

        self.inventory.record_stock_movement(
            product_id,
            StockMovementInput(
                movement_type="issue",
                quantity=3,
                note="Issued to administration",
            ),
        )
        self.assertEqual(self.inventory.get_product(product_id)["quantity"], 2)

        movement_count = len(self.inventory.list_stock_movements(product_id))
        with self.assertRaises(ConflictError):
            self.inventory.record_stock_movement(
                product_id,
                StockMovementInput(movement_type="issue", quantity=3),
            )

        self.assertEqual(self.inventory.get_product(product_id)["quantity"], 2)
        self.assertEqual(
            len(self.inventory.list_stock_movements(product_id)), movement_count
        )

        received = self.inventory.record_stock_movement(
            product_id,
            StockMovementInput(movement_type="receive", quantity=4),
        )
        self.assertEqual(received["movement_type"], "receive")
        self.assertEqual(self.inventory.get_product(product_id)["quantity"], 6)
        self.assertEqual(len(self.inventory.list_stock_movements(product_id)), 3)

        with self.assertRaises(ConflictError):
            self.inventory.delete_product(product_id)

    def test_duplicate_identifiers_and_invalid_relations_are_rejected(self) -> None:
        category = self.create_category()
        with self.assertRaises(ConflictError):
            self.inventory.create_category(CategoryInput(name="office supplies"))
        with self.assertRaises(NotFoundError):
            self.create_product(category_id=999)

        self.create_product(int(category["id"]))
        with self.assertRaises(ConflictError):
            self.inventory.create_product(
                ProductCreate(
                    name="Another paper",
                    sku="paper-a4",
                    category_id=int(category["id"]),
                )
            )

    def test_unused_category_and_product_can_be_deleted(self) -> None:
        category = self.create_category()
        product = self.create_product(int(category["id"]))
        self.inventory.delete_product(int(product["id"]))
        self.inventory.delete_category(int(category["id"]))

        self.assertEqual(self.inventory.list_products(), [])
        self.assertEqual(self.inventory.list_categories(), [])

    def test_movement_quantity_must_be_positive(self) -> None:
        with self.assertRaises(ValidationError):
            StockMovementInput(movement_type="receive", quantity=0)


if __name__ == "__main__":
    unittest.main()
