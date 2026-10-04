import json
from datetime import timedelta
from app.models.intelligence import BusinessEvent


class BusinessEventLogger:
    """
    Persists operational incident metadata into the PostgreSQL `business_events` table.
    Serves as the durable ground-truth answer key for downstream causal engine (Stage 7).
    """

    def __init__(self, db):
        self.db = db

    def log_incidents(self, incidents, simulation_log=None):
        """
        Takes the generated list of incidents from IncidentEngine (post-simulation)
        and logs each incident as one or more BusinessEvent records in PostgreSQL.
        Pulls exact PO receipt dates from simulation_log for supply-side incidents.
        """
        po_events = simulation_log.get("po_events", []) if simulation_log else []
        for inc in incidents:
            self._log_single_incident(inc, po_events)
        self.db.flush()

    def _get_actual_po_receipt_date(self, inc_id, fallback_end_date, po_events):
        """
        Looks up actual receipt date from simulated PO transactions matching inc_id specifically.
        Does NOT perform generic supplier fallback to avoid picking up unrelated future PO reorders.
        """
        matching = [e for e in po_events if e.get("incident_id") == inc_id and "receipt_date" in e]
        if matching:
            return matching[-1]["receipt_date"]
        return fallback_end_date

    def _log_single_incident(self, inc, po_events):
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
                description=json.dumps(desc_payload),
            )

        elif inc_type == "no_incident":
            # Negative control -- omitted from ground truth table
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
                description=json.dumps(desc_payload),
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
                description=json.dumps(desc_payload),
            )

        elif inc_type == "overlapping_supplier_delay":
            supplier_ids = inc.get("supplier_ids", [])
            duration_days = int(inc.get("duration_days", 0))
            offset_days = int(inc.get("start_offset_days", 0))

            for idx, supp_id in enumerate(supplier_ids):
                # Stagger second supplier by offset_days
                supp_start = start_date + timedelta(days=idx * offset_days)
                supp_end = supp_start + timedelta(days=max(0, duration_days - 1))
                self._create_event(
                    event_type="overlapping_supplier_delay",
                    entity_type="supplier",
                    entity_id=supp_id,
                    start_date=supp_start,
                    end_date=supp_end,
                    metric_name="delay_days",
                    metric_value=float(duration_days),
                    metric_unit="days",
                    baseline_value=0.0,
                    threshold_value=1.0,
                    status="Logged",
                    description=json.dumps(desc_payload),
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
                    description=json.dumps(desc_payload),
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
                    description=json.dumps(desc_payload),
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
                description=json.dumps(desc_payload),
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
                description=json.dumps(desc_payload),
            )

        elif inc_type == "severe_supplier_delay_stockout":
            supp_id = inc["supplier_id"]
            duration = float(inc.get("duration_days", 80))
            fallback_end = start_date + timedelta(days=int(duration))
            actual_end = self._get_actual_po_receipt_date(inc_id, fallback_end, po_events)
            observed_days = float((actual_end - start_date).days) if actual_end else duration

            desc_payload["intervention_duration_days"] = duration
            desc_payload["observed_delay_days"] = observed_days

            self._create_event(
                event_type="severe_supplier_delay",
                entity_type="supplier",
                entity_id=supp_id,
                start_date=start_date,
                end_date=actual_end,
                metric_name="delay_days",
                metric_value=duration,
                metric_unit="days",
                baseline_value=0.0,
                threshold_value=1.0,
                status="Logged",
                description=json.dumps(desc_payload),
            )

        elif inc_type == "seasonal_demand":
            prod_id = inc["product_id"]
            desc_payload["note"] = "Normal Q4 calendar seasonality; no artificial demand multiplier injected."
            self._create_event(
                event_type="seasonal_demand",
                entity_type="product",
                entity_id=prod_id,
                start_date=start_date,
                end_date=end_date,
                metric_name="demand_multiplier",
                metric_value=1.0,
                metric_unit="multiplier",
                baseline_value=1.0,
                threshold_value=1.0,
                status="Logged",
                description=json.dumps(desc_payload),
            )

    def _create_event(self, event_type, entity_type, entity_id, start_date, end_date,
                      metric_name, metric_value, metric_unit, baseline_value,
                      threshold_value, status, description):
        # Allow PostgreSQL auto-increment primary key sequence to assign id naturally
        event = BusinessEvent(
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
