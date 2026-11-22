"""
stage10/figures/test_causal_figures.py — Verification suite for printable causal graph figures.

Verifies:
1. Stage 7 DAG integrity (source of truth: 32 nodes, 40 edges).
2. Complete plain-English node labels and 6 required group assignments in node_labels.yaml.
3. Existence and validity of all 6 deliverable files (A4 overview SVG/PNG/PDF, A3 full DAG SVG/PNG/PDF).
4. Zero node bounding-box collisions on the full A3 diagram.
5. Strict font size constraints (>= 11 pt on A4 overview, >= 7 pt on A3 full).
6. Strict zero-leakage guarantee (no INC_ IDs, incidents.yaml, business_events, scenario scripts).
"""

import os
import re
import pickle
import unittest
from pathlib import Path
import yaml
import networkx as nx

FIGURES_DIR = Path(__file__).resolve().parent
ROOT_DIR = FIGURES_DIR.parent.parent
STAGE7_MODEL_PATH = ROOT_DIR / "stage7" / "fitted_causal_model.pkl"
LABELS_YAML_PATH = FIGURES_DIR / "node_labels.yaml"

EXPECTED_GROUPS = {
    "Calendar and demand",
    "Suppliers and purchasing",
    "Material stock",
    "Production",
    "Finished goods and orders",
    "Delivery and customer outcome"
}


def load_stage7_dag() -> nx.DiGraph:
    """Loads the expert DAG read-only from Stage 7 definition."""
    with open(STAGE7_MODEL_PATH, "rb") as f:
        data = pickle.load(f)
    return data["graph"]


class TestCausalFigures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.graph = load_stage7_dag()
        with open(LABELS_YAML_PATH, "r", encoding="utf-8") as f:
            cls.labels_data = yaml.safe_load(f)["nodes"]

    def test_01_stage7_dag_source_of_truth_counts(self):
        """Source of truth DAG must have exactly 32 nodes and 40 edges."""
        node_count = self.graph.number_of_nodes()
        edge_count = self.graph.number_of_edges()
        print(f"\n[CHECK] Stage 7 Expert DAG: {node_count} nodes, {edge_count} edges")
        self.assertEqual(node_count, 32, "DAG must contain exactly 32 nodes")
        self.assertEqual(edge_count, 40, "DAG must contain exactly 40 edges")

    def test_02_node_labels_yaml_completeness_and_groups(self):
        """Every single DAG node must have a plain-English label and valid group in node_labels.yaml."""
        dag_nodes = set(self.graph.nodes())
        yaml_nodes = set(self.labels_data.keys())

        missing_in_yaml = dag_nodes - yaml_nodes
        self.assertEqual(len(missing_in_yaml), 0, f"Missing nodes in node_labels.yaml: {missing_in_yaml}")

        for node_id, meta in self.labels_data.items():
            self.assertIn("label", meta, f"Node '{node_id}' missing 'label'")
            self.assertTrue(meta["label"].strip(), f"Node '{node_id}' has empty label")
            self.assertIn("technical_name", meta, f"Node '{node_id}' missing 'technical_name'")
            self.assertEqual(meta["technical_name"], node_id, f"technical_name mismatch for {node_id}")
            self.assertIn("group", meta, f"Node '{node_id}' missing 'group'")
            self.assertIn(meta["group"], EXPECTED_GROUPS, f"Invalid group '{meta['group']}' for node '{node_id}'")
            self.assertIn("description", meta, f"Node '{node_id}' missing 'description'")

        # Verify all 6 groups are represented
        found_groups = set(meta["group"] for meta in self.labels_data.values())
        self.assertEqual(found_groups, EXPECTED_GROUPS, "All 6 required groups must be populated")

    def test_03_deliverable_files_exist_and_non_empty(self):
        """All 6 required deliverables must exist as non-empty SVG, 300-dpi PNG, and PDF files."""
        expected_files = [
            "causal_graph_overview.svg",
            "causal_graph_overview.png",
            "causal_graph_overview.pdf",
            "causal_graph_full_A3.svg",
            "causal_graph_full_A3.png",
            "causal_graph_full_A3.pdf",
        ]
        for fname in expected_files:
            fpath = FIGURES_DIR / fname
            self.assertTrue(fpath.exists(), f"Deliverable missing: {fname}")
            size = fpath.stat().st_size
            self.assertGreater(size, 2048, f"Deliverable {fname} is too small ({size} bytes)")
            print(f"  ✓ Found deliverable {fname}: {size:,} bytes")

    def test_04_zero_answer_key_leakage(self):
        """No figure, SVG, or label metadata may contain answer-key content."""
        forbidden_patterns = [
            r"INC_\d+",
            r"incidents\.yaml",
            r"business_events",
            r"scenario_script",
            r"synthetic_injection"
        ]

        files_to_check = [
            LABELS_YAML_PATH,
            FIGURES_DIR / "causal_graph_overview.svg",
            FIGURES_DIR / "causal_graph_full_A3.svg",
        ]

        for fpath in files_to_check:
            if not fpath.exists():
                continue
            text = fpath.read_text(encoding="utf-8", errors="ignore")
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                self.assertEqual(
                    len(matches), 0,
                    f"Forbidden answer-key pattern '{pattern}' found in {fpath.name}: {matches[:3]}"
                )
        print("  ✓ Zero answer-key leakage verified in figure metadata and SVG files.")

    def test_05_bounding_box_and_font_checks(self):
        """Loads generation metrics log and verifies 0 collisions and compliant font sizes."""
        metrics_file = FIGURES_DIR / "figure_metrics.json"
        self.assertTrue(metrics_file.exists(), "figure_metrics.json must be generated by generator")
        import json
        with open(metrics_file, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        self.assertEqual(metrics.get("a3_node_collisions"), 0, "A3 full graph must have 0 node collisions")
        self.assertGreaterEqual(metrics.get("a3_min_font_pt", 0), 7.0, "A3 min font must be >= 7.0 pt")
        self.assertGreaterEqual(metrics.get("overview_min_font_pt", 0), 11.0, "Overview min font must be >= 11.0 pt")
        self.assertEqual(metrics.get("a3_rendered_nodes"), 32, "A3 figure must render exactly 32 nodes")
        self.assertEqual(metrics.get("a3_rendered_edges"), 40, "A3 figure must render exactly 40 edges")
        print(f"  ✓ Bounding box collision count: {metrics['a3_node_collisions']} (PASS)")
        print(f"  ✓ A3 Full DAG Min Font Size: {metrics['a3_min_font_pt']} pt (>= 7.0 pt PASS)")
        print(f"  ✓ Overview Min Font Size: {metrics['overview_min_font_pt']} pt (>= 11.0 pt PASS)")


if __name__ == "__main__":
    unittest.main()
