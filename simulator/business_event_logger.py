import json
from app.models.intelligence import BusinessEvent


class BusinessEventLogger:
    """
    Persists operational incident metadata into the PostgreSQL `business_events` table.
    Serves as the durable ground-truth answer key for downstream causal engine (Stage 7).
    """

    def __init__(self, db):
        self.db = db
        self.next_event_id = 1

    def log_incidents(self, incidents):
        """
        Takes the generated list of incidents from IncidentEngine and logs
        each incident as one or more BusinessEvent records in PostgreSQL.
        """
        for inc in incidents:
            self._log_single_incident(inc)
        self.db.flush()

    def _log_single_incident(self, inc):
        inc_type = inc["type"]
        inc_id = inc["id"]
        start_date = inc["start_date"]
        end_date = inc["end_date"]
        causal_role = inc.get("causal_role", {})

        desc_payload = {
            "incident_id": inc_id,
            "category": inc.get("category", "operational"),
            "causal_role": causal_role,
        }
        desc_json = json.dumps(desc_payload)

        if inc_type == "supplier_delay":
            supplier_id = inc["supplier_id"]
            duration = float(inc.get("duration_days", 0))
            self._create_event(
                event_type="supplier_delay",
                entity_type="supplier",
                entity_id=supplier_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="delay_days",
                metric_value=duration,
                metric_unit="days",
                baseline_value=0.0,
                threshold_value=1.0,
                status="Logged",
                description=desc_json,
            )

        elif inc_type == "no_incident":
            # Negative control -- omit logging or log baseline operational marker if needed
            pass

        elif inc_type == "demand_spike":
            product_id = inc["product_id"]
            mult = float(inc.get("demand_multiplier", 1.0))
            self._create_event(
                event_type="demand_spike",
                entity_type="product",
                entity_id=product_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="demand_multiplier",
                metric_value=mult,
                metric_unit="multiplier",
                baseline_value=1.0,
                threshold_value=1.2,
                status="Logged",
                description=desc_json,
            )

        elif inc_type == "capacity_disruption":
            product_id = inc["product_id"]
            red = float(inc.get("capacity_reduction", 0.0))
            self._create_event(
                event_type="capacity_disruption",
                entity_type="product",
                entity_id=product_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="capacity_reduction",
                metric_value=red,
                metric_unit="ratio",
                baseline_value=0.0,
                threshold_value=0.1,
                status="Logged",
                description=desc_json,
            )

        elif inc_type == "overlapping_supplier_delay":
            supplier_ids = inc.get("supplier_ids", [])
            duration = float(inc.get("duration_days", 0))
            for supp_id in supplier_ids:
                self._create_event(
                    event_type="overlapping_supplier_delay",
                    entity_type="supplier",
                    entity_id=supp_id,
                    start_date=start_date,
                    end_date=end_date,
                    metric_name="delay_days",
                    metric_value=duration,
                    metric_unit="days",
                    baseline_value=0.0,
                    threshold_value=1.0,
                    status="Logged",
                    description=desc_json,
                )

        elif inc_type == "two_simultaneous_independent_causes":
            supp_id = inc.get("supplier_id")
            prod_id = inc.get("product_id")
            duration = float(inc.get("duration_days", 0))
            red = float(inc.get("capacity_reduction", 0.0))

            if supp_id:
                self._create_event(
                    event_type="independent_supplier_delay",
                    entity_type="supplier",
                    entity_id=supp_id,
                    start_date=start_date,
                    end_date=end_date,
                    metric_name="delay_days",
                    metric_value=duration,
                    metric_unit="days",
                    baseline_value=0.0,
                    threshold_value=1.0,
                    status="Logged",
                    description=desc_json,
                )
            if prod_id:
                self._create_event(
                    event_type="indep_capacity_disruption",
                    entity_type="product",

                    entity_id=prod_id,
                    start_date=start_date,
                    end_date=end_date,
                    metric_name="capacity_reduction",
                    metric_value=red,
                    metric_unit="ratio",
                    baseline_value=0.0,
                    threshold_value=0.1,
                    status="Logged",
                    description=desc_json,
                )

        elif inc_type == "partial_receipt":
            supp_id = inc["supplier_id"]
            frac = float(inc.get("received_fraction", 1.0))
            self._create_event(
                event_type="partial_receipt",
                entity_type="supplier",
                entity_id=supp_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="received_fraction",
                metric_value=frac,
                metric_unit="fraction",
                baseline_value=1.0,
                threshold_value=0.9,
                status="Logged",
                description=desc_json,
            )

        elif inc_type == "delay_absorbed_by_safety_stock":
            supp_id = inc["supplier_id"]
            duration = float(inc.get("duration_days", 0))
            self._create_event(
                event_type="delay_absorbed",
                entity_type="supplier",
                entity_id=supp_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="delay_days",
                metric_value=duration,
                metric_unit="days",
                baseline_value=0.0,
                threshold_value=1.0,
                status="Logged",
                description=desc_json,
            )

        elif inc_type == "severe_supplier_delay_stockout":
            supp_id = inc["supplier_id"]
            duration = float(inc.get("duration_days", 0))
            self._create_event(
                event_type="severe_supplier_delay",
                entity_type="supplier",
                entity_id=supp_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="delay_days",
                metric_value=duration,
                metric_unit="days",
                baseline_value=0.0,
                threshold_value=1.0,
                status="Logged",
                description=desc_json,
            )

        elif inc_type == "seasonal_demand":
            prod_id = inc["product_id"]
            mult = float(inc.get("demand_multiplier", 1.3))
            self._create_event(
                event_type="seasonal_demand",
                entity_type="product",
                entity_id=prod_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="demand_multiplier",
                metric_value=mult,
                metric_unit="multiplier",
                baseline_value=1.0,
                threshold_value=1.1,
                status="Logged",
                description=desc_json,
            )

    def _create_event(self, event_type, entity_type, entity_id, start_date, end_date,
                      metric_name, metric_value, metric_unit, baseline_value,
                      threshold_value, status, description):
        event = BusinessEvent(
            id=self.next_event_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            occurred_start_date=start_date,
            occurred_end_date=end_date,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            baseline_value=baseline_value,
            threshold_value=threshold_value,
            status=status,
            description=description,
        )
        self.db.add(event)
        self.next_event_id += 1
