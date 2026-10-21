# SAGE Operational Day-Pack Specification (v6)

A **Day-Pack** represents exactly one calendar day of transactional events exported from an Enterprise Resource Planning (ERP) or Manufacturing Execution System (MES).

Directory naming convention: `demo_data/packs/<YYYY-MM-DD>/`

## Required Files and Schemas

Each day-pack directory must contain a `metadata.json` file and up to 6 transactional CSV files:

### 1. `metadata.json`
```json
{
  "pack_date": "YYYY-MM-DD",
  "created_at": "ISO-8601-UTC-TIMESTAMP",
  "source_system": "ERP/MES",
  "data_classification": "simulated"
}
```

### 2. `purchase_orders.csv`
Purchase orders created on `pack_date`.
* `id` (integer, Primary Key)
* `supplier_id` (integer, Foreign Key to Supplier)
* `order_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `expected_delivery_date` (date, YYYY-MM-DD)
* `status` (string, computed as-of `pack_date`, e.g. "Open")

### 3. `goods_receipts.csv`
Goods receipts recorded on `pack_date`.
* `id` (integer, Primary Key)
* `po_id` (integer, Foreign Key to PurchaseOrder)
* `receipt_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `carrier` (string)

### 4. `sales_orders.csv`
Sales orders created on `pack_date`.
* `id` (integer, Primary Key)
* `customer_id` (integer, Foreign Key to Customer)
* `order_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `delivery_due_date` (date, YYYY-MM-DD)
* `status` (string, computed as-of `pack_date`, e.g. "Open" or "Backordered")

### 5. `deliveries.csv`
Customer order shipments dispatched on `pack_date`.
* `id` (integer, Primary Key)
* `order_id` (integer, Foreign Key to SalesOrder)
* `delivery_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `carrier` (string)

### 6. `production_orders.csv`
Work orders and production runs scheduled or completed on `pack_date`.
* `id` (integer, Primary Key)
* `product_id` (integer, Foreign Key to Product)
* `start_date` (date, YYYY-MM-DD)
* `due_date` (date, YYYY-MM-DD)
* `quantity` (numeric)
* `status` (string, e.g. "Completed", "In Progress")

### 7. `stock_movements.csv`
Inventory ledger debits and credits recorded on `pack_date`.
* `id` (integer, Primary Key)
* `item_id` (integer, Foreign Key to InventoryItem)
* `quantity` (numeric, positive for receipt/production, negative for issue/shipment)
* `movement_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `reference_type` (string, e.g. "PO_RECEIPT", "SO_DELIVERY", "PRODUCTION_ISSUE")
* `reference_id` (integer)

## Ingestion Rules & Guards
1. **Strict Temporal Boundary**: Every row must have its primary event date equal to `pack_date`. Zero future-dated rows allowed.
2. **Sequential Precedence**: Packs must be ingested in continuous sequential order (`current_day + 1 day`). No skipping or repeating dates.
3. **No Future Leakage**: Status fields (e.g., `status: "Received"`) must reflect only events known up to `pack_date`.
4. **Atomic Rejection**: Any violation rejects the whole pack; no partial commits are made.
