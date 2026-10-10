"""FastAPI routes for the stockroom inventory system."""

from fastapi import FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.database import initialize_database
from app.models import (
    Category,
    CategoryInput,
    Product,
    ProductCreate,
    ProductInput,
    StockMovement,
    StockMovementInput,
)
from app.services import ConflictError, InventoryService, NotFoundError

app = FastAPI(
    title="Stockroom Inventory API",
    description=(
        "Track categorized supplies, current stock, reorder levels, "
        "and receive/issue transactions."
    ),
    version="1.0.0",
)
inventory = InventoryService()


@app.exception_handler(NotFoundError)
async def handle_not_found(_request: Request, error: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(ConflictError)
async def handle_conflict(_request: Request, error: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.get("/")
def home() -> dict[str, str]:
    return {
        "message": "Stockroom Inventory API",
        "docs": "/docs",
        "health": "ok",
    }


@app.get("/categories", response_model=list[Category])
def get_categories() -> list[dict[str, object]]:
    return inventory.list_categories()


@app.get("/categories/{category_id}", response_model=Category)
def get_category(category_id: int) -> dict[str, object]:
    return inventory.get_category(category_id)


@app.post(
    "/categories",
    response_model=Category,
    status_code=status.HTTP_201_CREATED,
)
def create_category(category: CategoryInput) -> dict[str, object]:
    return inventory.create_category(category)


@app.put("/categories/{category_id}", response_model=Category)
def update_category(
    category_id: int, category: CategoryInput
) -> dict[str, object]:
    return inventory.update_category(category_id, category)


@app.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int) -> Response:
    inventory.delete_category(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/products", response_model=list[Product])
def get_products(
    q: str | None = Query(default=None, description="Search name, SKU, or description"),
    category_id: int | None = Query(default=None, ge=1),
) -> list[dict[str, object]]:
    return inventory.list_products(query=q, category_id=category_id)


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int) -> dict[str, object]:
    return inventory.get_product(product_id)


@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate) -> dict[str, object]:
    return inventory.create_product(product)


@app.put("/products/{product_id}", response_model=Product)
def update_product(product_id: int, product: ProductInput) -> dict[str, object]:
    return inventory.update_product(product_id, product)


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int) -> Response:
    inventory.delete_product(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/inventory/low-stock", response_model=list[Product])
def get_low_stock_products() -> list[dict[str, object]]:
    return inventory.list_low_stock_products()


@app.post(
    "/products/{product_id}/movements",
    response_model=StockMovement,
    status_code=status.HTTP_201_CREATED,
)
def record_stock_movement(
    product_id: int, movement: StockMovementInput
) -> dict[str, object]:
    return inventory.record_stock_movement(product_id, movement)


@app.get("/stock-movements", response_model=list[StockMovement])
def get_stock_movements(
    product_id: int | None = Query(default=None, ge=1),
) -> list[dict[str, object]]:
    return inventory.list_stock_movements(product_id)


initialize_database()
