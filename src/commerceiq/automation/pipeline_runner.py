#!/usr/bin/env python3
"""
CommerceIQ — Pillar 5: Analytics Automation & Monitoring Engine
===============================================================
Coordinates automated warehouse health checks, scheduled KPI evaluation against
`config/kpi_registry.json`, threshold alert generation, BI mart refresh, and
structured execution logging with full error handling.
"""

import os
import json
import logging
from datetime import datetime, timezone
import pandas as pd
from commerceiq.db_engine import CommerceIQWarehouse


class CommerceIQAutomationRunner:
    def __init__(self, warehouse: CommerceIQWarehouse, output_dir: str, log_dir: str):
        self.warehouse = warehouse
        self.output_dir = output_dir
        self.log_dir = log_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.log_file = os.path.join(self.log_dir, "automation_execution.log")
        self.logger = logging.getLogger("CommerceIQAutomation")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            fh = logging.FileHandler(self.log_file, mode="w")
            fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self.logger.addHandler(fh)

    def evaluate_kpi(self, kpi_def: dict) -> float:
        sql = f"SELECT {kpi_def['sql_expression']} AS val FROM {kpi_def['source_view']}"
        df = self.warehouse.query_df(sql)
        return float(df["val"].iloc[0])

    def run_automated_pipeline(self, validation_summary: dict) -> dict:
        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        self.logger.info(f"Starting CommerceIQ automated pipeline run {run_id}")

        # Step 1: Data Quality Gate Check
        failed_dq = validation_summary.get("failed", 0)
        dq_gate_passed = failed_dq == 0
        self.logger.info(
            f"Data Quality Gate: passed={validation_summary.get('passed')}, "
            f"warnings={validation_summary.get('warnings')}, failed={failed_dq} -> GatePassed={dq_gate_passed}"
        )
        if not dq_gate_passed:
            raise RuntimeError(f"Data Quality Gate halted pipeline: {failed_dq} failed checks.")

        # Step 2: Scheduled KPI Calculation & Threshold Alerting
        registry = self.warehouse.load_kpi_registry()
        kpi_snapshots = []
        triggered_alerts = []

        for kpi in registry["kpis"]:
            try:
                val = self.evaluate_kpi(kpi)
                rule = kpi.get("alert_rule")
                breached = False
                if rule:
                    op = rule["operator"]
                    thresh = float(rule["threshold"])
                    if op == "<" and val < thresh:
                        breached = True
                    elif op == ">" and val > thresh:
                        breached = True

                snap = {
                    "kpi_id": kpi["kpi_id"],
                    "name": kpi["name"],
                    "domain": kpi["domain"],
                    "value": val,
                    "unit": kpi["unit"],
                    "provenance": kpi["provenance"],
                    "threshold_breached": breached,
                }
                kpi_snapshots.append(snap)
                self.logger.info(f"Evaluated KPI {kpi['kpi_id']} = {val} ({kpi['unit']}) | Breached={breached}")

                if breached:
                    alert = {
                        "kpi_id": kpi["kpi_id"],
                        "kpi_name": kpi["name"],
                        "observed_value": val,
                        "operator": rule["operator"],
                        "threshold": rule["threshold"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "recommended_ai_investigation": f"Trigger CommerceIQAIOrchestrator on '{kpi['name']}'",
                    }
                    triggered_alerts.append(alert)
                    self.logger.warning(f"ALERT [{rule['severity']}]: {rule['message']} (observed={val})")
            except Exception as exc:
                self.logger.error(f"Error evaluating KPI {kpi['kpi_id']}: {exc}")
                raise

        report_payload = {
            "run_id": run_id,
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_quality_gate": {
                "status": "PASSED" if dq_gate_passed else "FAILED",
                **validation_summary,
            },
            "evaluated_kpis_count": len(kpi_snapshots),
            "kpi_snapshots": kpi_snapshots,
            "triggered_alerts_count": len(triggered_alerts),
            "triggered_alerts": triggered_alerts,
            "log_file": "logs/automation_execution.log",
        }

        out_json = os.path.join(self.output_dir, "automation_run_report.json")
        with open(out_json, "w") as f:
            json.dump(report_payload, f, indent=2)

        self.logger.info(f"Completed automated pipeline {run_id} successfully. Alerts={len(triggered_alerts)}")
        return report_payload
