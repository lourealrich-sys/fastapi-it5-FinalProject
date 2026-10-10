"""Pydantic models for inventory API requests and responses."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CategoryInput(BaseModel):
    """Fields accepted when creating or updating a product category."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank.")
        return value


class Category(CategoryInput):
    """A stored product category."""

    id: int


class ProductInput(BaseModel):
    """Fields accepted when updating product details."""

    name: str = Field(min_length=1, max_length=150)
    sku: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    category_id: int = Field(gt=0)
    reorder_level: int = Field(default=0, ge=0)

    @field_validator("name", "sku")
    @classmethod
    def text_fields_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class ProductCreate(ProductInput):
    """Fields accepted when creating a product, including its starting stock."""

    initial_quantity: int = Field(default=0, ge=0)


class Product(ProductInput):
    """A stored product and its current stock level."""

    id: int
    quantity: int
    created_at: str
    updated_at: str


class StockMovementInput(BaseModel):
    """A request to receive new stock or issue stock from inventory."""

    movement_type: Literal["receive", "issue"]
    quantity: int = Field(gt=0)
    note: str = Field(default="", max_length=500)


class StockMovement(BaseModel):
    """An immutable record of a stock transaction."""

    id: int
    product_id: int
    movement_type: Literal["receive", "issue"]
    quantity: int
    note: str
    created_at: str
