"""
IncidentEngine — Stage 4 of SAGE.

Decides WHEN incidents happen and WHAT their input parameters are.
Does NOT pre-compute downstream effects.
"""

import hashlib
import random
import yaml
from datetime import date, timedelta


def is_production_day(current_day, seed=42):
    if current_day.weekday() >= 5:
        return False
    date_str = current_day.isoformat() if hasattr(current_day, "isoformat") else str(current_day)
    seed_str = f"{seed}_production_day_{date_str}_0_"
    seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()
    seed_int = int(seed_hash[:15], 16)
    return random.Random(seed_int).random() < 0.28


class IncidentEngine:

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

        self.incident_types = [
            incident for incident in self.config["incidents"]
            if incident.get("enabled", True)
        ]

        self._entity_usage = {}
        self._placed_windows = []

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
            pool = selection.get("candidates", self.suppliers)
            return {"supplier_id": self._pick_under_cap(pool, "supplier")}

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
            return {
                "supplier_id": self._pick_under_cap(self.suppliers, "supplier"),
                "product_id": self._pick_under_cap(self.finished_products, "product"),
            }

        return {}

    def _windows_conflict(self, start, end):
        for existing_start, existing_end in self._placed_windows:
            gap_start = existing_start - timedelta(days=self.min_gap_days)
            gap_end = existing_end + timedelta(days=self.min_gap_days)
            if start <= gap_end and end >= gap_start:
                return True
        return False

    def _place_window(self, incident_id, duration_days, max_attempts=500, schedule_within=None, min_production_days=0):
        if schedule_within:
            window_start = date(2025, schedule_within["start_month"], 1)
            end_month = schedule_within["end_month"]
            window_end = (
                date(2025, 12, 31) if end_month == 12
                else date(2025, end_month + 1, 1) - timedelta(days=1)
            )
            earliest = max(self.start_date, window_start)
            latest_start = min(self.end_date - timedelta(days=duration_days - 1), window_end - timedelta(days=duration_days - 1))
        else:
            earliest = self.start_date
            latest_start = (
                self.end_date
                - timedelta(days=duration_days - 1)
                - timedelta(days=self.SCHEDULING_MARGIN_DAYS)
            )

        total_days = (latest_start - earliest).days
        if total_days < 0:
            raise RuntimeError(
                f"schedule_within window too narrow to fit a {duration_days}-day incident."
            )

        # Isolated placement RNG stream keyed on (seed, 'placement', incident_id)
        # Guarantees placement retries for one incident never consume numbers from
        # self.rng or perturb any other incident's placement stream.
        date_str = date(2025, 1, 1).isoformat()
        seed_str = f"{self.seed}_placement_{date_str}_0_{incident_id}"
        seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()
        seed_int = int(seed_hash[:15], 16)
        place_rng = random.Random(seed_int)

        for _ in range(max_attempts):
            offset = place_rng.randint(0, total_days)
            start = earliest + timedelta(days=offset)
            end = start + timedelta(days=duration_days - 1)
            if not self._windows_conflict(start, end):
                if min_production_days > 0:
                    prod_count = sum(
                        1 for i in range((end - start).days + 1)
                        if is_production_day(start + timedelta(days=i), self.seed)
                    )
                    if prod_count < min_production_days:
                        continue
                self._placed_windows.append((start, end))
                return start, end

        raise RuntimeError(
            f"Could not place incident {incident_id} without violating min_gap_days or min_production_days."
        )

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

        if "target_material" in incident:
            result["material_id"] = incident["target_material"]

        placement_duration = incident.get("placement_duration_override", generated_duration)
        start, end = self._place_window(
            incident["id"],
            placement_duration,
            schedule_within=incident.get("schedule_within"),
            min_production_days=incident.get("requires_production_days", 0),
        )
        result["start_date"] = start
        result["end_date"] = end

        causal_role = incident.get("causal_role", {})
        result["expected_effects"] = causal_role.get(
            "expected_path", causal_role.get("expected_paths", [])
        )

        return result

    def generate(self):
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