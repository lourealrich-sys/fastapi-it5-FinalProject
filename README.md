# Stockroom Inventory API

A small FastAPI and SQLite application for a school, community group, or small
office supply room. It helps a stockroom attendant answer two practical
questions: **what supplies are available, and what was received or issued?**
Keeping quantities and movement history together reduces manual counting
mistakes and helps staff notice supplies that need reordering.

## Run on Windows

From the project folder, create and activate a virtual environment, install the
dependencies, and start the API:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open <http://127.0.0.1:8000/docs> to try the endpoints in Swagger UI. The API
creates `inventory.db` in the project folder when it starts.

## How the system is organized

- `main.py` defines the FastAPI endpoints and translates expected inventory
  errors to HTTP responses.
- `app/models.py` contains Pydantic request and response models, including
  validation for positive movement quantities and required text.
- `app/services.py` defines the `InventoryService` class. It owns category,
  product, search, and stock movement operations.
- `app/database.py` manages SQLite connections and initializes the schema.

The database has three related tables:

- `categories` stores a category name and description.
- `products` belongs to one category through `category_id`; its current
  `quantity` cannot be negative.
- `stock_movements` references a product and records each received or issued
  quantity, note, and timestamp. The movement history is retained, so a
  product with recorded movements cannot be deleted.

Foreign keys are enabled on every SQLite connection. Category names and product
SKUs are unique without regard to letter case. Categories that still contain
products cannot be deleted.

## Typical workflow

1. Create a category, for example `Office supplies`.
2. Create a product in that category and optionally record its starting stock.
3. Receive new supplies or issue supplies to a staff member/department by
   recording a stock movement.
4. Search products, check low-stock items, or review a product's movement
   history before placing a reorder.

For example, create a category:

```http
POST /categories
Content-Type: application/json

{
  "name": "Office supplies",
  "description": "Paper and writing materials"
}
```

Then create a product using the returned `id` as `category_id`:

```http
POST /products
Content-Type: application/json

{
  "name": "A4 copy paper",
  "sku": "PAPER-A4",
  "description": "Box of 5 reams",
  "category_id": 1,
  "reorder_level": 3,
  "initial_quantity": 10
}
```

Issue two boxes:

```http
POST /products/1/movements
Content-Type: application/json

{
  "movement_type": "issue",
  "quantity": 2,
  "note": "Issued to the administration office"
}
```

The service updates the product quantity and inserts its movement record in one
SQLite transaction. If the requested issue exceeds available stock, the
transaction is rolled back, stock is unchanged, and the API returns HTTP 409.
Receiving uses the same endpoint with `"movement_type": "receive"`. Initial
stock supplied during product creation is also recorded as a receive movement.

## API reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Welcome message and documentation link |
| `GET` | `/categories` | List categories |
| `GET` | `/categories/{category_id}` | Get one category |
| `POST` | `/categories` | Create a category |
| `PUT` | `/categories/{category_id}` | Update a category |
| `DELETE` | `/categories/{category_id}` | Delete an unused category |
| `GET` | `/products` | List products; optional `q` and `category_id` filters |
| `GET` | `/products/{product_id}` | Get one product |
| `POST` | `/products` | Create a product with optional `initial_quantity` |
| `PUT` | `/products/{product_id}` | Update product details and reorder level |
| `DELETE` | `/products/{product_id}` | Delete a product with no movement history |
| `GET` | `/inventory/low-stock` | List products at or below their reorder level |
| `POST` | `/products/{product_id}/movements` | Receive or issue stock |
| `GET` | `/stock-movements` | List movement history; optional `product_id` filter |

Invalid request fields return HTTP 422. Missing records return HTTP 404.
Duplicate category names or SKUs, attempts to delete related records, and
attempts to issue more stock than is available return HTTP 409.

## Implementation concepts

The Pydantic model classes separate request validation from database records.
The `InventoryService` class groups responsibilities around the stockroom
workflow, while `database_connection` handles commit, rollback, and cleanup.
SQL values are passed with placeholders rather than concatenated into queries.
Category/product CRUD, text search, and the receive/issue transaction together
provide a connected inventory process rather than unrelated example records.

## Tests

Run the focused inventory service tests with:

```powershell
python -m unittest discover -s tests
```
