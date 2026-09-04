# SAGE Database Schema — v4 FINAL (20 tables)

## Part A — Operational (what happened)
1. Suppliers — id, name, region, base_lead_time_days, historical_on_time_rate
2. Purchase Orders — id, supplier_id, order_date, expected_delivery_date, status
3. Purchase Order Lines — id, po_id, material_id, quantity_ordered, quantity_received
4. Goods Receipts — id, po_id, receipt_date, status
5. Goods Receipt Lines — id, receipt_id, po_line_id, material_id, quantity_received
6. Products — id, name, category, unit_of_measure
7. Inventory Items — id, product_id (UNIQUE), safety_stock, reorder_point, opening_balance_qty, opening_balance_date
8. Stock Movements — id, item_id, date, movement_type, quantity, goods_receipt_line_id, material_issue_id, production_order_id, delivery_line_id (exactly one FK populated)
9. Bill of Materials — id, finished_good_id, raw_material_id, quantity_required (UNIQUE on the pair)
10. Production Orders — id, product_id, planned_start, planned_end, actual_start, actual_end, planned_qty, actual_qty, status
11. Material Issues — id, production_order_id, item_id, planned_quantity, planned_issue_date, quantity_issued, issue_date
12. Sales Orders — id, customer_id, order_date, requested_delivery_date, status
13. Sales Order Lines — id, sales_order_id, product_id, quantity_ordered, quantity_fulfilled
14. Deliveries — id, sales_order_id, ship_date, delivery_date (nullable), status
15. Delivery Lines — id, delivery_id, sales_order_line_id, product_id, quantity_shipped
16. Customers — id, name, region

## Part B — Intelligence (what SAGE found)
17. Business Events — id, event_type, entity_type, entity_id, occurred_start_date, occurred_end_date, metric_name, metric_value, metric_unit, baseline_value, threshold_value, status, description
18. Risks — id, event_id, assessed_at, risk_score, severity, affected_order_count, impact_description, priority_rank
19. Causal Analysis Runs — id, analysis_date, dag_version, baseline_window_start, baseline_window_end, comparison_window_start, comparison_window_end, random_seed, notes
20. Causal Attributions — id, analysis_run_id, effect_event_id, candidate_node, candidate_event_id, attribution_score, attribution_rank, path_nodes