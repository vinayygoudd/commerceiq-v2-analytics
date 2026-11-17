#!/usr/bin/env python3
"""
CommerceIQ — Capability 3: Intelligent Anomaly Detection (Isolation Forest + LLM)
=================================================================================
Detects unusual changes in weekly revenue (GMV), order volume, average order
value (AOV), and active customer activity using Scikit-Learn `IsolationForest`
and rolling statistical z-scores, quantifies the BRL business impact of each
anomaly, and generates natural-language explanations via Google Gemini (with
deterministic database-grounded explanations as fallback).
"""

import os
import json
import numpy as np
import pandas as pd
from commerceiq.db_engine import CommerceIQWarehouse
from commerceiq.ai.nl_to_sql import call_gemini_api

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class CommerceIQAnomalyDetector:
    def __init__(self, warehouse: CommerceIQWarehouse, output_dir: str = None, bi_mart_dir: str = None, api_key: str = None):
        self.warehouse = warehouse
        self.output_dir = output_dir or os.path.join(warehouse.platform_root, "outputs")
        self.bi_mart_dir = bi_mart_dir or os.path.join(warehouse.platform_root, "bi", "powerbi_star_schema")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.bi_mart_dir, exist_ok=True)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def detect_anomalies(self, contamination: float = 0.08) -> dict:
        sql_weekly = """
        SELECT
            STRFTIME('%Y-W%W', SUBSTR(order_purchase_timestamp, 1, 10)) AS order_year_week,
            MIN(SUBSTR(order_purchase_timestamp, 1, 10)) AS week_start_date,
            COUNT(DISTINCT order_id) AS orders_count,
            COUNT(DISTINCT customer_unique_id) AS active_customers,
            ROUND(SUM(gross_item_revenue_brl), 2) AS gmv_brl,
            ROUND(SUM(gross_item_revenue_brl) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS aov_brl,
            ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
            ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct,
            ROUND(100.0 * SUM(has_return) / NULLIF(COUNT(*), 0), 2) AS return_rate_pct
        FROM vw_fact_order_items
        WHERE order_purchase_timestamp >= '2017-01-01'
        GROUP BY 1
        HAVING COUNT(DISTINCT order_id) >= 10
        ORDER BY 1;
        """
        df = self.warehouse.query_df(sql_weekly)
        if df.empty:
            df = self.warehouse.query_df(
                """
                SELECT
                    order_year_month AS order_year_week,
                    order_year_month || '-01' AS week_start_date,
                    COUNT(DISTINCT order_id) AS orders_count,
                    COUNT(DISTINCT customer_unique_id) AS active_customers,
                    ROUND(SUM(gross_item_revenue_brl), 2) AS gmv_brl,
                    ROUND(SUM(gross_item_revenue_brl) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS aov_brl,
                    ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
                    ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct,
                    ROUND(100.0 * SUM(has_return) / NULLIF(COUNT(*), 0), 2) AS return_rate_pct
                FROM vw_fact_order_items
                GROUP BY 1
                ORDER BY 1;
                """
            )

        feature_cols = ["gmv_brl", "orders_count", "aov_brl", "active_customers"]
        for col in feature_cols:
            roll_mean = df[col].rolling(window=6, min_periods=1).mean()
            roll_std = df[col].rolling(window=6, min_periods=1).std().replace(0, np.nan).fillna(df[col].std() or 1.0)
            df[f"{col}_baseline"] = roll_mean.round(2)
            df[f"{col}_zscore"] = ((df[col] - roll_mean) / roll_std.replace(0, 1.0)).round(2)

        df["gmv_impact_brl"] = (df["gmv_brl"] - df["gmv_brl_baseline"]).round(2)
        df["orders_impact"] = (df["orders_count"] - df["orders_count_baseline"]).round(0)

        if HAS_SKLEARN and len(df) >= 5:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(df[feature_cols].fillna(0.0))
            iso = IsolationForest(contamination=min(max(contamination, 0.05), 0.25), random_state=42)
            preds = iso.fit_predict(X_scaled)
            scores = -iso.score_samples(X_scaled)
            df["is_anomaly"] = np.where((preds == -1) | (df["gmv_brl_zscore"].abs() >= 2.2), 1, 0)
            df["anomaly_severity_score"] = np.round(scores, 4)
            method_used = "Scikit-Learn IsolationForest + 6-Week Rolling Z-Score"
        else:
            z_matrix = np.column_stack([df[f"{c}_zscore"].fillna(0.0).to_numpy() for c in feature_cols])
            multivariate_score = np.sqrt(np.mean(z_matrix ** 2, axis=1))
            df["anomaly_severity_score"] = np.round(multivariate_score, 4)
            df["is_anomaly"] = np.where((multivariate_score >= 1.8) | (df["gmv_brl_zscore"].abs() >= 2.0), 1, 0)
            if df["is_anomaly"].sum() == 0 and len(df) > 0:
                df.loc[df["anomaly_severity_score"].idxmax(), "is_anomaly"] = 1
            method_used = "Multivariate Statistical Z-Score + Isolation Envelope"

        def classify_pattern(row):
            if row["is_anomaly"] == 0:
                return "Normal"
            if row["gmv_brl_zscore"] >= 1.5:
                return "Revenue & Order Surge (Peak Event / Black Friday)"
            if row["gmv_brl_zscore"] <= -1.5:
                return "Revenue & Volume Drop"
            if abs(row["aov_brl_zscore"]) >= 1.5:
                return "Average Order Value (AOV) Shift"
            return "Multivariate Activity Anomaly"

        df["anomaly_type"] = df.apply(classify_pattern, axis=1)

        mart_path = os.path.join(self.bi_mart_dir, "mart_anomaly_events.csv")
        df.to_csv(mart_path, index=False)

        anomalies_df = df[df["is_anomaly"] == 1].sort_values("anomaly_severity_score", ascending=False)
        anomalies_list = anomalies_df.to_dict("records")

        total_positive_impact = float(anomalies_df[anomalies_df["gmv_impact_brl"] > 0]["gmv_impact_brl"].sum()) if not anomalies_df.empty else 0.0
        total_negative_impact = float(anomalies_df[anomalies_df["gmv_impact_brl"] < 0]["gmv_impact_brl"].sum()) if not anomalies_df.empty else 0.0

        llm_prompt = (
            "You are a senior e-commerce anomaly detection analyst. Explain the following detected anomalies "
            "in weekly revenue (GMV), orders, AOV, and active customers in 3 concise bullet points, quantifying "
            "their BRL business impact:\n"
            f"{json.dumps(anomalies_list[:6], indent=2)}"
        )
        llm_explanation = call_gemini_api(llm_prompt, api_key=self.api_key)
        explanation_mode = "gemini_llm" if llm_explanation else "deterministic_grounded_explanation"

        if not llm_explanation:
            bullets = []
            for row in anomalies_list[:5]:
                sign = "+" if row["gmv_impact_brl"] >= 0 else ""
                bullets.append(
                    f"- **{row['order_year_week']} ({row['week_start_date']}) — {row['anomaly_type']}:** "
                    f"GMV reached R$ {row['gmv_brl']:,.2f} ({sign}R$ {row['gmv_impact_brl']:,.2f} vs. rolling baseline, "
                    f"z={row['gmv_brl_zscore']:.2f}), with {int(row['orders_count']):,} orders, "
                    f"{int(row['active_customers']):,} active customers, and R$ {row['aov_brl']:.2f} AOV."
                )
            llm_explanation = "\n".join(bullets) if bullets else "No severe weekly anomalies exceeded isolation thresholds."

        payload = {
            "method": method_used,
            "explanation_mode": explanation_mode,
            "total_periods_analyzed": int(len(df)),
            "anomalies_detected_count": int(len(anomalies_df)),
            "quantified_business_impact": {
                "positive_surge_gmv_delta_brl": round(total_positive_impact, 2),
                "negative_drop_gmv_delta_brl": round(total_negative_impact, 2),
            },
            "detected_anomalies": anomalies_list,
            "natural_language_explanation": llm_explanation,
            "powerbi_mart_exported": mart_path,
        }

        out_json = os.path.join(self.output_dir, "anomaly_detection_results.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        md_lines = [
            "# CommerceIQ — Intelligent Anomaly Detection Report",
            "",
            f"**Detection Engine:** `{payload['method']}` | **Explanation Mode:** `{explanation_mode}`",
            f"**Periods Analyzed:** `{payload['total_periods_analyzed']}` | **Anomalies Flagged:** `{payload['anomalies_detected_count']}`",
            "",
            "## 1. Quantified Business Impact",
            f"- **Positive Surge GMV Delta vs. Rolling Baseline:** `R$ {total_positive_impact:,.2f}`",
            f"- **Negative Drop GMV Delta vs. Rolling Baseline:** `R$ {total_negative_impact:,.2f}`",
            "",
            "## 2. AI Natural-Language Explanation of Top Anomalies",
            llm_explanation,
        ]
        out_md = os.path.join(self.output_dir, "anomaly_detection_report.md")
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

        return payload