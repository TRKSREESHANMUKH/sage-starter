"""
build_causal_model.py — SAGE Stage 7: Expert-Defined Causal DAG Construction & Fitting.

Research Framing:
"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

Strict Zero-Leakage Guarantee:
This script loads ONLY analytics/daily_panel_baseline.parquet and master data tables.
It NEVER imports BusinessEvent or queries business_events.
"""

import os
import sys
import pickle
import pandas as pd
import numpy as np
import networkx as nx
import dowhy.gcm as gcm

from app.database import SessionLocal
from app.models.inventory import InventoryItem, BillOfMaterials
from app.models.suppliers import Supplier


MATERIALS = [101, 102, 103]
PRODUCTS = [201, 202]
SUPPLIERS = [1, 2, 3, 4, 5]

SUPPLIERS_FOR_MATERIAL = {
    101: [1, 2, 4],   # steel
    102: [3, 4],      # plastic
    103: [1, 5],      # copper
}


def build_dag_with_audit(boms):
    """
    Constructs the expert-defined Causal DiGraph dynamically from master data mappings
    and attaches comprehensive edge audit metadata.
    """
    edges = []
    edge_audit = {}

    # 1. Material stock nodes: parents = lag1 + supplier delays + supplier fill rates
    for m in MATERIALS:
        mat_node = f"material_{m}_stock"

        # Lag edge
        u, v = f"material_{m}_stock_lag1", mat_node
        edges.append((u, v))
        edge_audit[(u, v)] = {
            "source": u, "target": v,
            "mechanism": "Autoregressive inventory continuity (yesterday closing stock carries over)",
            "temporal_direction": "lagged (t-1 -> t)",
            "relationship_type": "autoregressive_state_lag",
            "feature_name": u
        }

        supp_list = SUPPLIERS_FOR_MATERIAL.get(m, [])
        for s in supp_list:
            # Delay edge
            u_delay = f"supplier_{s}_po_delay_days"
            edges.append((u_delay, mat_node))
            edge_audit[(u_delay, mat_node)] = {
                "source": u_delay, "target": mat_node,
                "mechanism": "Purchase order shipment delay reduces material receipts and depletes stock",
                "temporal_direction": "contemporaneous (t -> t)",
                "relationship_type": "exogenous_supply_driver",
                "feature_name": u_delay
            }

            # Fill rate edge
            u_fill = f"supplier_{s}_receipt_fill_rate"
            edges.append((u_fill, mat_node))
            edge_audit[(u_fill, mat_node)] = {
                "source": u_fill, "target": mat_node,
                "mechanism": "Partial order fulfillment reduces received quantity into stock",
                "temporal_direction": "contemporaneous (t -> t)",
                "relationship_type": "exogenous_supply_driver",
                "feature_name": u_fill
            }

    # 2. Customer Demand nodes: parents = weekday, month
    for p in PRODUCTS:
        dem_node = f"product_{p}_demand_units"

        edges.append(("weekday", dem_node))
        edge_audit[("weekday", dem_node)] = {
            "source": "weekday", "target": dem_node,
            "mechanism": "Day-of-week seasonality (higher orders on business days)",
            "temporal_direction": "contemporaneous calendar (t -> t)",
            "relationship_type": "calendar_context",
            "feature_name": "weekday"
        }

        edges.append(("month", dem_node))
        edge_audit[("month", dem_node)] = {
            "source": "month", "target": dem_node,
            "mechanism": "Monthly / Q4 seasonal order volume boost",
            "temporal_direction": "contemporaneous calendar (t -> t)",
            "relationship_type": "calendar_context",
            "feature_name": "month"
        }

    # 3. Actual Production nodes: parents = planned_prod, capacity_shortfall_units, material stocks
    bom_map = {}
    for b in boms:
        bom_map.setdefault(b.finished_good_id, []).append(b.raw_material_id)

    for p in PRODUCTS:
        prod_node = f"product_{p}_actual_production"

        u_plan = f"product_{p}_planned_production"
        edges.append((u_plan, prod_node))
        edge_audit[(u_plan, prod_node)] = {
            "source": u_plan, "target": prod_node,
            "mechanism": "Master production schedule baseline target",
            "temporal_direction": "contemporaneous (t -> t)",
            "relationship_type": "operational_plan_target",
            "feature_name": u_plan
        }

        u_cap = f"product_{p}_capacity_shortfall_units"
        edges.append((u_cap, prod_node))
        edge_audit[(u_cap, prod_node)] = {
            "source": u_cap, "target": prod_node,
            "mechanism": "Machine downtime or labor shortage limits achievable production output",
            "temporal_direction": "contemporaneous (t -> t)",
            "relationship_type": "exogenous_capacity_driver",
            "feature_name": u_cap
        }

        mats_for_prod = bom_map.get(p, [])
        for m in mats_for_prod:
            u_mat = f"material_{m}_stock"
            edges.append((u_mat, prod_node))
            edge_audit[(u_mat, prod_node)] = {
                "source": u_mat, "target": prod_node,
                "mechanism": "Raw material inventory availability constrains factory manufacturing",
                "temporal_direction": "contemporaneous (t -> t)",
                "relationship_type": "mediated_stock_driver",
                "feature_name": u_mat
            }

    # 4. FG Stock nodes: parents = fg_stock_lag1, actual_production, demand_units
    for p in PRODUCTS:
        fg_node = f"product_{p}_fg_stock"

        u_fg_lag = f"product_{p}_fg_stock_lag1"
        edges.append((u_fg_lag, fg_node))
        edge_audit[(u_fg_lag, fg_node)] = {
            "source": u_fg_lag, "target": fg_node,
            "mechanism": "Yesterday closing finished goods inventory state carries over",
            "temporal_direction": "lagged (t-1 -> t)",
            "relationship_type": "autoregressive_state_lag",
            "feature_name": u_fg_lag
        }

        u_prod = f"product_{p}_actual_production"
        edges.append((u_prod, fg_node))
        edge_audit[(u_prod, fg_node)] = {
            "source": u_prod, "target": fg_node,
            "mechanism": "Daily manufactured units added to finished goods warehouse inventory",
            "temporal_direction": "contemporaneous (t -> t)",
            "relationship_type": "mediated_production_flow",
            "feature_name": u_prod
        }

        u_dem = f"product_{p}_demand_units"
        edges.append((u_dem, fg_node))
        edge_audit[(u_dem, fg_node)] = {
            "source": u_dem, "target": fg_node,
            "mechanism": "Daily customer order fulfillments drawn from finished goods warehouse inventory",
            "temporal_direction": "contemporaneous (t -> t)",
            "relationship_type": "exogenous_demand_flow",
            "feature_name": u_dem
        }

    # 5. Due Backlog nodes: parents = fg_stock, demand_units
    for p in PRODUCTS:
        backlog_node = f"product_{p}_due_backlog_units"

        u_fg = f"product_{p}_fg_stock"
        edges.append((u_fg, backlog_node))
        edge_audit[(u_fg, backlog_node)] = {
            "source": u_fg, "target": backlog_node,
            "mechanism": "Finished goods inventory depletion triggers unfulfilled order backlogs",
            "temporal_direction": "contemporaneous (t -> t)",
            "relationship_type": "mediated_inventory_state",
            "feature_name": u_fg
        }

        u_dem = f"product_{p}_demand_units"
        edges.append((u_dem, backlog_node))
        edge_audit[(u_dem, backlog_node)] = {
            "source": u_dem, "target": backlog_node,
            "mechanism": "High customer order volume exceeding available inventory increases backlogs",
            "temporal_direction": "contemporaneous (t -> t)",
            "relationship_type": "exogenous_demand_driver",
            "feature_name": u_dem
        }

    graph = nx.DiGraph(edges)
    return graph, edge_audit


def prepare_baseline_data(db_session, panel_path="analytics/daily_panel_baseline.parquet"):
    if not os.path.exists(panel_path):
        raise FileNotFoundError(f"Baseline panel file not found: {panel_path}")

    df = pd.read_parquet(panel_path)
    inv_items = {101: 200.0, 102: 200.0, 103: 200.0, 201: 50.0, 202: 50.0}
    if db_session:
        try:
            inv_items.update({item.product_id: float(item.opening_balance_qty) for item in db_session.query(InventoryItem).all()})
        except Exception:
            pass

    for m in MATERIALS:
        open_bal = inv_items.get(m, 200.0)
        df[f"material_{m}_stock_lag1"] = df[f"material_{m}_stock"].shift(1).fillna(open_bal)

    for p in PRODUCTS:
        open_bal = inv_items.get(p, 50.0)
        df[f"product_{p}_fg_stock_lag1"] = df[f"product_{p}_fg_stock"].shift(1).fillna(open_bal)

    return df


def main():
    print("=" * 70)
    print("STAGE 7: BUILDING & FITTING EXPERT CAUSAL DAG (DOWHY GCM)")
    print("Research Framing:")
    print("  'SAGE performs controlled synthetic causal-attribution evaluation under an")
    print("   expert-defined causal model; it does not claim to prove real-world causality.'")
    print("=" * 70)

    boms = []
    db = None
    try:
        db = SessionLocal()
        boms = db.query(BillOfMaterials).all()
    except Exception:
        class MockBOM:
            def __init__(self, fg_id, rm_id):
                self.finished_good_id = fg_id
                self.raw_material_id = rm_id
        boms = [MockBOM(201, 101), MockBOM(201, 102), MockBOM(201, 103), MockBOM(202, 101), MockBOM(202, 103)]

    graph, edge_audit = build_dag_with_audit(boms)
    print(f"\nFULL CAUSAL GRAPH EDGE AUDIT ({len(graph.edges())} NetworkX DiGraph Edges):")
    for idx, ((u, v), meta) in enumerate(edge_audit.items(), 1):
        print(f"  {idx:2d}. {u:38s} ---> {v:32s} | {meta['relationship_type']:28s} | {meta['temporal_direction']}")

    baseline_df = prepare_baseline_data(db)
    if db:
        try:
            db.close()
        except Exception:
            pass

    print(f"\nBaseline Dataset Loaded: {baseline_df.shape[0]} rows x {baseline_df.shape[1]} columns")

    causal_model = gcm.StructuralCausalModel(graph)

    print("\nAutomatically assigning causal mechanisms...")
    gcm.auto.assign_causal_mechanisms(causal_model, baseline_df, quality=gcm.auto.AssignmentQuality.GOOD)

    print("Fitting Causal Model on Baseline Panel...")
    gcm.fit(causal_model, baseline_df)

    os.makedirs("stage7", exist_ok=True)
    model_path = "stage7/fitted_causal_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({"causal_model": causal_model, "graph": graph, "edge_audit": edge_audit}, f)

    print(f"\nFitted Causal Model successfully saved to: {model_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
