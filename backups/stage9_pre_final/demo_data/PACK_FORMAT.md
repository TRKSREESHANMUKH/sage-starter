# SAGE Operational Day-Pack Specification (Stage 9 FINAL)

> **Mandatory Research Framing:**
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

A **Day-Pack** represents exactly one calendar day of transactional events exported from an Enterprise Resource Planning (ERP) or Manufacturing Execution System (MES).

Directory naming convention: `demo_data/packs/<YYYY-MM-DD>/`

## Required Files and Schemas

Each day-pack directory must contain `metadata.json` and 11 transactional CSV files matching the operational table models:

### 1. `metadata.json`
```json
{
  "pack_date": "YYYY-MM-DD",
  "is_simulated": true,
  "label": "SIMULATED ERP OPERATIONAL PACK",
  "framing": "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality.",
  "exported_at": "ISO-8601-UTC-TIMESTAMP",
  "row_counts": { ... },
  "total_events": 0
}
```

### 2. `purchase_orders.csv`
Purchase orders created on `pack_date`.
* `id` (integer, Primary Key)
* `supplier_id` (integer, Foreign Key to Supplier)
* `order_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `expected_delivery_date` (date, YYYY-MM-DD)
* `status` (string, computed as-of `pack_date`, e.g. "Pending", "Partial", "Complete")

### 3. `purchase_order_lines.csv`
* `id` (integer, Primary Key)
* `po_id` (integer, Foreign Key to purchase_orders)
* `material_id` (integer, Foreign Key to products)
* `quantity_ordered` (integer)
* `quantity_received` (integer, as of `pack_date`)

### 4. `goods_receipts.csv`
Goods receipts recorded on `pack_date`.
* `id` (integer, Primary Key)
* `po_id` (integer, Foreign Key to purchase_orders)
* `receipt_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `status` (string, e.g. "Received")

### 5. `goods_receipt_lines.csv`
* `id` (integer, Primary Key)
* `receipt_id` (integer, Foreign Key to goods_receipts)
* `po_line_id` (integer, Foreign Key to purchase_order_lines)
* `material_id` (integer, Foreign Key to products)
* `quantity_received` (integer)

### 6. `sales_orders.csv`
Sales orders created on `pack_date`.
* `id` (integer, Primary Key)
* `customer_id` (integer, Foreign Key to customers)
* `order_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `requested_delivery_date` (date, YYYY-MM-DD)
* `status` (string, computed as-of `pack_date`, e.g. "Pending", "Partial", "Complete", "Backorder")

### 7. `sales_order_lines.csv`
* `id` (integer, Primary Key)
* `sales_order_id` (integer, Foreign Key to sales_orders)
* `product_id` (integer, Foreign Key to products)
* `quantity_ordered` (integer)
* `quantity_fulfilled` (integer, as of `pack_date`)

### 8. `deliveries.csv`
Customer order shipments dispatched on `pack_date`.
* `id` (integer, Primary Key)
* `sales_order_id` (integer, Foreign Key to sales_orders)
* `ship_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `delivery_date` (date, YYYY-MM-DD)
* `status` (string, e.g. "Delivered", "Dispatched")

### 9. `delivery_lines.csv`
* `id` (integer, Primary Key)
* `delivery_id` (integer, Foreign Key to deliveries)
* `sales_order_line_id` (integer, Foreign Key to sales_order_lines)
* `product_id` (integer, Foreign Key to products)
* `quantity_shipped` (integer)

### 10. `production_orders.csv`
Manufacturing orders planned or executed on `pack_date`.
* `id` (integer, Primary Key)
* `product_id` (integer, Foreign Key to products)
* `planned_start` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `planned_end` (date, YYYY-MM-DD)
* `actual_start` (date, YYYY-MM-DD, nullable)
* `actual_end` (date, YYYY-MM-DD, nullable)
* `planned_qty` (integer)
* `actual_qty` (integer, nullable)
* `status` (string, e.g. "Completed", "Delayed", "In Progress")

### 11. `material_issues.csv`
Raw material issues for manufacturing on `pack_date`.
* `id` (integer, Primary Key)
* `production_order_id` (integer, Foreign Key to production_orders)
* `item_id` (integer, Foreign Key to inventory_items)
* `planned_quantity` (integer)
* `planned_issue_date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `quantity_issued` (integer, nullable)
* `issue_date` (date, YYYY-MM-DD, nullable)

### 12. `stock_movements.csv`
Inventory ledger debits (OUT) and credits (IN) recorded on `pack_date`.
* `id` (integer, Primary Key)
* `item_id` (integer, Foreign Key to inventory_items)
* `date` (date, YYYY-MM-DD, MUST equal `pack_date`)
* `movement_type` (string, "IN" or "OUT")
* `quantity` (numeric)
* `goods_receipt_line_id` (integer, nullable)
* `material_issue_id` (integer, nullable)
* `production_order_id` (integer, nullable)
* `delivery_line_id` (integer, nullable)

## Ingestion Rules & Guards
1. **Strict Temporal Boundary**: Every row must have its primary event date equal to `pack_date`. Zero past or future-dated rows allowed.
2. **Sequential Precedence**: Packs must be ingested in strictly continuous sequential order (`current_day + 1 day`). No skipping or repeating dates.
3. **No Future Leakage**: Status fields (e.g., `status: "Received"`, `quantity_fulfilled`) must reflect only events known up to `pack_date`.
4. **Atomic Ingestion**: Any schema mismatch, duplicate key, or date continuity violation rejects the entire pack with zero database modifications.
