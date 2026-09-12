"""
IncidentEngine — Stage 4 of SAGE.

Design principle (unchanged from project rules): this module ONLY decides
WHEN incidents happen and WHAT their input parameters are (e.g. a supplier
is delayed 5 days, demand is multiplied 1.7x). It does NOT decide, fake, or
pre-compute any downstream effect (stock levels, production output, sales
impact). Those must always be *calculated* by daily_simulation.py reacting
to these parameters as it runs day by day. `expected_path` in the yaml is
documentation for later causal-engine validation (Stage 7) — it is never
injected into the simulation as a real effect.

This engine always generates exactly the 10 frozen required scenarios
listed in incidents.yaml — nothing is randomly skipped or subsampled.
Only the entity assignment, exact parameter values within their configured
ranges, and placement in the calendar year are randomized (seeded, so a
given seed always reproduces the same incident set).
"""

import random
import yaml
from datetime import date, timedelta


class IncidentEngine:

    # Worst-case chain for a supply-side incident: supplier base_lead_time
    # (up to 14 days) + the normal on-time/late roll (up to 7 days) + the
    # incident's own added delay (up to 14 days) = ~35 days before a
    # receipt even happens, plus we want some room afterward for the
    # downstream production/sales effect to actually show up in the log
    # before the year ends. 60 days gives real margin without meaningfully
    # shrinking the usable scheduling window (year is 365 days; only 10
    # incidents with 10-day gaps need to fit).
    SCHEDULING_MARGIN_DAYS = 60

    def __init__(self, config_path="simulator/incidents.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        sim_cfg = self.config["simulation"]
        self.seed = sim_cfg["seed"]
        self.min_gap_days = sim_cfg["min_gap_days"]
        self.max_incidents_per_entity = sim_cfg["max_incidents_per_entity"]

        self.rng = random.Random(self.seed)

        self.start_date = date(2025, 1, 1)
        self.end_date = date(2025, 12, 31)

        self.suppliers = [1, 2, 3, 4, 5]
        self.finished_products = [201, 202]

        # Always ALL enabled incidents — no subsampling. Order preserved
        # from the yaml so scenario numbering stays stable and readable.
        self.incident_types = [
            incident for incident in self.config["incidents"]
            if incident.get("enabled", True)
        ]

        # Tracks how many incidents have touched each entity so far,
        # so max_incidents_per_entity can actually be enforced.
        self._entity_usage = {}

        # Tracks (start_date, end_date) of every incident placed so far,
        # so min_gap_days can actually be enforced.
        self._placed_windows = []

    # ------------------------------------------------------------------
    # Random value / entity helpers
    # ------------------------------------------------------------------

    def random_number(self, value):
        if isinstance(value, dict):
            minimum, maximum = value["min"], value["max"]
            if isinstance(minimum, int) and isinstance(maximum, int):
                return self.rng.randint(minimum, maximum)
            return round(self.rng.uniform(minimum, maximum), 3)
        return value

    def _usage_count(self, entity_key):
        return self._entity_usage.get(entity_key, 0)

    def _bump_usage(self, entity_key):
        self._entity_usage[entity_key] = self._usage_count(entity_key) + 1

    def _pick_under_cap(self, candidates, entity_prefix):
        """Pick from candidates, preferring ones still under the
        per-entity incident cap. Falls back to full candidate list only
        if every candidate is already at/over cap (keeps things running
        even with a small entity pool)."""
        under_cap = [
            c for c in candidates
            if self._usage_count(f"{entity_prefix}:{c}") < self.max_incidents_per_entity
        ]
        pool = under_cap if under_cap else candidates
        choice = self.rng.choice(pool)
        self._bump_usage(f"{entity_prefix}:{choice}")
        return choice

    def choose_entity(self, incident):
        selection = incident.get("selection", {})
        entity = selection.get("entity")

        if entity == "supplier":
            return {"supplier_id": self._pick_under_cap(self.suppliers, "supplier")}

        if entity == "finished_product":
            return {"product_id": self._pick_under_cap(self.finished_products, "product")}

        if entity == "multiple_suppliers":
            count = self.random_number(selection.get("count", {"min": 2, "max": 2}))
            count = min(count, len(self.suppliers))
            chosen = []
            remaining = list(self.suppliers)
            for _ in range(count):
                pick = self._pick_under_cap(remaining, "supplier")
                chosen.append(pick)
                remaining.remove(pick)
            return {"supplier_ids": chosen}

        if entity == "independent_pair":
            # One supplier-side root cause + one production-side root
            # cause, deliberately unrelated to each other.
            return {
                "supplier_id": self._pick_under_cap(self.suppliers, "supplier"),
                "product_id": self._pick_under_cap(self.finished_products, "product"),
            }

        # id 19 / no_incident and any entity-less incident
        return {}

    # ------------------------------------------------------------------
    # Scheduling: placing all 10 incidents across the year with a
    # minimum gap between any two incident windows.
    # ------------------------------------------------------------------

    def _windows_conflict(self, start, end):
        for existing_start, existing_end in self._placed_windows:
            gap_start = existing_start - timedelta(days=self.min_gap_days)
            gap_end = existing_end + timedelta(days=self.min_gap_days)
            if start <= gap_end and end >= gap_start:
                return True
        return False

    def _place_window(self, duration_days, max_attempts=500):
        """Find a start date such that [start, start+duration) keeps at
        least min_gap_days away from every previously placed window, AND
        leaves SCHEDULING_MARGIN_DAYS of runway before END_DATE so the
        incident's full consequence (lead time, receipt, downstream
        effect) has time to actually happen and be observed."""
        latest_start = (
            self.end_date
            - timedelta(days=duration_days - 1)
            - timedelta(days=self.SCHEDULING_MARGIN_DAYS)
        )
        total_days = (latest_start - self.start_date).days

        for _ in range(max_attempts):
            offset = self.rng.randint(0, total_days)
            start = self.start_date + timedelta(days=offset)
            end = start + timedelta(days=duration_days - 1)
            if not self._windows_conflict(start, end):
                self._placed_windows.append((start, end))
                return start, end

        raise RuntimeError(
            "Could not place incident without violating min_gap_days — "
            "year is too packed for the current min_gap_days/incident count. "
            "Widen the year, reduce min_gap_days, or reduce incident count."
        )

    # ------------------------------------------------------------------
    # Building individual incidents
    # ------------------------------------------------------------------

    def create_incident(self, incident):
        result = {
            "id": incident["id"],
            "type": incident["type"],
            "category": incident["category"],
        }

        parameters = incident.get("parameters", {})
        generated_duration = 1

        for key, value in parameters.items():
            generated_value = self.random_number(value)
            result[key] = generated_value
            if "duration" in key:
                generated_duration = int(generated_value)

        result.update(self.choose_entity(incident))

        start, end = self._place_window(generated_duration)
        result["start_date"] = start
        result["end_date"] = end

        causal_role = incident.get("causal_role", {})
        result["expected_effects"] = causal_role.get(
            "expected_path", causal_role.get("expected_paths", [])
        )

        return result

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self):
        """Always returns exactly the 10 frozen scenarios, each scheduled
        to respect min_gap_days and max_incidents_per_entity. Sorted by
        start_date for a readable, chronological incident log."""
        self._entity_usage = {}
        self._placed_windows = []

        incidents = [self.create_incident(inc) for inc in self.incident_types]
        incidents.sort(key=lambda i: i["start_date"])
        return incidents


if __name__ == "__main__":
    engine = IncidentEngine()
    incidents = engine.generate()

    print("\nGenerated Incidents (all 10 frozen scenarios)")
    print("=" * 70)
    for incident in incidents:
        print(
            f"{incident['id']:8} {incident['type']:35} "
            f"{incident['start_date']} -> {incident['end_date']}"
        )
        print(f"    {incident}\n")