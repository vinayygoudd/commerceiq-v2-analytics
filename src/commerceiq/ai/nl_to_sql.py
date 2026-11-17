#!/usr/bin/env python3
"""
CommerceIQ — Capability 1: LLM-Based Natural Language to SQL Engine
===================================================================
Integrates Google Gemini (with automatic SDK / REST detection and deterministic
SQL fallback) to translate plain-English business questions into validated,
read-only SQLite queries grounded in `get_schema_catalog()` and `kpi_registry.json`.
"""

import os
import re
import json
import urllib.request
import urllib.error
import pandas as pd
from commerceiq.db_engine import CommerceIQWarehouse

FORBIDDEN_SQL_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
}


def call_gemini_api(prompt: str, api_key: str = None, model: str = "gemini-2.5-flash") -> str:
    """
    Calls Google Gemini using google-genai, google-generativeai, or standard REST API.
    Returns None if no API key is configured or if the network call fails.
    """
    key = (api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        return None

    # 1. Try modern google-genai SDK
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=key)
        resp = client.models.generate_content(model=model, contents=prompt)
        if resp and getattr(resp, "text", None):
            return resp.text.strip()
    except Exception:
        pass

    # 2. Try google-generativeai SDK
    try:
        import google.generativeai as genai_legacy  # type: ignore

        genai_legacy.configure(api_key=key)
        m = genai_legacy.GenerativeModel(model)
        resp = m.generate_content(prompt)
        if resp and getattr(resp, "text", None):
            return resp.text.strip()
    except Exception:
        pass

    # 3. Fallback to zero-dependency HTTPS REST call
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"].strip()
    except Exception:
        return None
    return None


class CommerceIQNLToSQL:
    def __init__(self, warehouse: CommerceIQWarehouse, output_dir: str = None, api_key: str = None):
        self.warehouse = warehouse
        self.output_dir = output_dir or os.path.join(warehouse.platform_root, "outputs")
        os.makedirs(self.output_dir, exist_ok=True)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        try:
            self.kpi_registry = warehouse.load_kpi_registry()
        except Exception:
            self.kpi_registry = {"kpis": []}
        self.schema_catalog = warehouse.get_schema_catalog()

    def match_kpi(self, question: str) -> dict:
        q = question.lower()
        kpis = {k.get("kpi_id", ""): k for k in self.kpi_registry.get("kpis", [])}
        mapping = [
            (["repeat", "retention", "cohort", "loyalty", "churn"], "repeat_purchase_rate_pct", "Customer Repeat Purchase Rate %"),
            (["margin", "profit", "cogs", "contribution", "underperform"], "net_contribution_margin_pct", "Net Contribution Margin %"),
            (["late", "delivery", "carrier", "shipping", "logistics", "sla"], "delivered_late_rate_pct", "Late Delivery Rate %"),
            (["roas", "marketing", "campaign", "cac", "ad", "channel"], "paid_marketing_roas", "Paid Marketing ROAS"),
            (["return", "rma", "refund"], "post_delivery_return_rate_pct", "Post-Delivery Item Return Rate %"),
            (["cancel"], "order_cancellation_rate_pct", "Order Cancellation Rate %"),
            (["stockout", "inventory", "sku", "warehouse"], "inventory_stockout_rate_pct", "Monthly SKU-Seller Stockout Rate %"),
            (["ticket", "support", "csat"], "support_sla_breach_rate_pct", "Support Ticket 48h SLA Breach Rate %"),
            (["session", "funnel", "conversion"], "session_to_order_conversion_pct", "Session-to-Order Placement Conversion %"),
        ]
        for keywords, kpi_id, default_name in mapping:
            if any(w in q for w in keywords):
                return kpis.get(kpi_id, {"kpi_id": kpi_id, "name": default_name})
        return kpis.get(
            "gross_merchandise_value_brl",
            {"kpi_id": "gross_merchandise_value_brl", "name": "Gross Merchandise Value (GMV)"},
        )

    @staticmethod
    def extract_clean_sql(raw_text: str) -> str:
        if not raw_text:
            return ""
        fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw_text, flags=re.IGNORECASE | re.DOTALL)
        sql = fenced.group(1).strip() if fenced else raw_text.strip()
        sql = re.sub(r"^SQL\s*:\s*", "", sql, flags=re.IGNORECASE).strip()
        return sql.rstrip(";").strip() + ";"

    def validate_sql(self, sql: str) -> dict:
        """
        Validates that a SQL string is a single, read-only SELECT/WITH query
        and verifies its syntax and schema via SQLite EXPLAIN QUERY PLAN.
        """
        if not sql or not sql.strip():
            return {"is_valid": False, "reason": "Empty SQL query."}

        cleaned = sql.strip()
        # Strip trailing semicolon to check for multi-statement injection
        body = cleaned[:-1].strip() if cleaned.endswith(";") else cleaned
        if ";" in body:
            return {"is_valid": False, "reason": "Multiple SQL statements are prohibited."}

        upper_tokens = set(re.findall(r"\b[A-Z_]+\b", body.upper()))
        forbidden_hit = upper_tokens.intersection(FORBIDDEN_SQL_KEYWORDS)
        if forbidden_hit:
            return {
                "is_valid": False,
                "reason": f"Forbidden non-read-only keyword(s) detected: {', '.join(sorted(forbidden_hit))}",
            }

        if not (body.upper().startswith("SELECT") or body.upper().startswith("WITH")):
            return {"is_valid": False, "reason": "Query must begin with SELECT or WITH."}

        conn = self.warehouse.get_connection()
        try:
            plan = conn.execute(f"EXPLAIN QUERY PLAN {body}").fetchall()
            return {"is_valid": True, "reason": "Validated read-only SELECT query.", "query_plan": [str(r) for r in plan]}
        except Exception as exc:
            return {"is_valid": False, "reason": f"SQLite schema/syntax error: {exc}"}
        finally:
            conn.close()

    def deterministic_fallback_sql(self, question: str) -> tuple:
        """
        Returns (sql_query, template_name) using verified analytical SQL templates.
        """
        q = question.lower()
        if any(w in q for w in ["margin", "profit", "contribution", "category", "underperform"]):
            return (
                """
                SELECT
                    product_category_english,
                    COUNT(*) AS units_sold,
                    ROUND(SUM(gross_item_revenue_brl), 2) AS gmv_brl,
                    ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
                    ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct,
                    ROUND(100.0 * SUM(has_return) / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END), 0), 2) AS return_rate_pct
                FROM vw_fact_order_items
                GROUP BY product_category_english
                HAVING COUNT(*) >= 300
                ORDER BY net_margin_pct ASC, gmv_brl DESC
                LIMIT 15;
                """.strip(),
                "deterministic_category_margin_analysis",
            )
        if any(w in q for w in ["repeat", "retention", "cohort", "churn", "loyalty"]):
            return (
                """
                SELECT
                    CASE
                        WHEN acquisition_cohort_ym BETWEEN '2017-01' AND '2017-06' THEN '2017-H1'
                        WHEN acquisition_cohort_ym BETWEEN '2017-07' AND '2017-12' THEN '2017-H2'
                        WHEN acquisition_cohort_ym >= '2018-01' THEN '2018'
                        ELSE 'Prior'
                    END AS cohort_window,
                    COUNT(*) AS customers_count,
                    SUM(is_repeat_customer) AS repeat_customers,
                    ROUND(100.0 * SUM(is_repeat_customer) / NULLIF(COUNT(*), 0), 2) AS repeat_rate_pct,
                    ROUND(AVG(lifetime_payment_brl), 2) AS avg_ltv_brl,
                    ROUND(100.0 * AVG(ever_had_late_delivery), 2) AS late_delivery_pct,
                    ROUND(AVG(avg_customer_review_score), 2) AS avg_review_score
                FROM vw_customer_summary
                GROUP BY 1
                ORDER BY 1;
                """.strip(),
                "deterministic_cohort_retention_analysis",
            )
        if any(w in q for w in ["late", "carrier", "delivery", "shipping", "logistics"]):
            return (
                """
                SELECT
                    carrier_name,
                    service_tier,
                    COUNT(*) AS delivered_shipments,
                    ROUND(100.0 * AVG(is_late_delivery), 2) AS late_delivery_pct,
                    ROUND(AVG(delivery_variance_days), 2) AS avg_variance_days,
                    ROUND(AVG(freight_margin_brl), 2) AS avg_freight_margin_brl,
                    ROUND(AVG(avg_review_score), 2) AS avg_review_score
                FROM vw_carrier_performance
                GROUP BY carrier_name, service_tier
                ORDER BY late_delivery_pct DESC;
                """.strip(),
                "deterministic_carrier_sla_analysis",
            )
        if any(w in q for w in ["roas", "marketing", "campaign", "cac", "channel", "ad"]):
            return (
                """
                SELECT
                    marketing_channel,
                    COUNT(*) AS campaigns_count,
                    ROUND(SUM(actual_spend_brl), 2) AS actual_spend_brl,
                    SUM(acquired_customers) AS acquired_customers,
                    ROUND(SUM(attributed_gmv_brl), 2) AS attributed_gmv_brl,
                    ROUND(SUM(attributed_gmv_brl) / NULLIF(SUM(actual_spend_brl), 0), 2) AS roas_x,
                    ROUND(SUM(actual_spend_brl) / NULLIF(SUM(acquired_customers), 0), 2) AS effective_cac_brl
                FROM vw_marketing_roas
                GROUP BY marketing_channel
                ORDER BY roas_x DESC;
                """.strip(),
                "deterministic_marketing_roas_analysis",
            )
        if any(w in q for w in ["session", "funnel", "conversion"]):
            return (
                """
                SELECT
                    funnel_stage_reached AS funnel_exit_stage,
                    COUNT(*) AS sessions_count,
                    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM commerceiq_customer_sessions_funnel), 2) AS pct_of_sessions,
                    SUM(CASE WHEN order_placed = 1 THEN 1 ELSE 0 END) AS orders_placed_count,
                    SUM(CASE WHEN order_delivered = 1 THEN 1 ELSE 0 END) AS orders_delivered_count
                FROM commerceiq_customer_sessions_funnel
                GROUP BY 1
                ORDER BY sessions_count DESC;
                """.strip(),
                "deterministic_session_funnel_analysis",
            )
        if any(w in q for w in ["support", "ticket", "csat", "sla"]):
            return (
                """
                SELECT
                    issue_category,
                    COUNT(*) AS tickets_count,
                    ROUND(AVG(first_response_time_minutes), 1) AS avg_first_response_min,
                    ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours,
                    ROUND(100.0 * AVG(sla_breached), 2) AS sla_breach_pct,
                    ROUND(AVG(csat_score), 2) AS avg_csat_score
                FROM commerceiq_customer_support_tickets
                GROUP BY issue_category
                ORDER BY sla_breach_pct DESC;
                """.strip(),
                "deterministic_support_sla_analysis",
            )
        if any(w in q for w in ["inventory", "stockout", "sku", "stock"]):
            return (
                """
                SELECT
                    snapshot_date,
                    COUNT(*) AS active_sku_seller_pairs,
                    SUM(opening_stock_units) AS opening_units,
                    SUM(units_received) AS received_units,
                    SUM(units_sold) AS sold_units,
                    SUM(closing_stock_units) AS closing_units,
                    SUM(available_to_promise_units) AS available_units,
                    SUM(CASE WHEN is_stockout = 1 THEN 1 ELSE 0 END) AS stockout_skus
                FROM commerceiq_inventory_snapshots
                GROUP BY snapshot_date
                ORDER BY snapshot_date;
                """.strip(),
                "deterministic_inventory_snapshot_analysis",
            )
        return (
            """
            SELECT
                order_year_month,
                COUNT(DISTINCT order_id) AS orders_count,
                ROUND(SUM(gross_item_revenue_brl), 2) AS gmv_brl,
                ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
                ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct,
                ROUND(SUM(gross_item_revenue_brl) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS aov_brl
            FROM vw_fact_order_items
            WHERE order_year_month >= '2017-01'
            GROUP BY order_year_month
            ORDER BY order_year_month;
            """.strip(),
            "deterministic_monthly_financial_trend",
        )

    def build_llm_sql_prompt(self, question: str, chat_history: list = None) -> str:
        views_only = [
            obj for obj in self.schema_catalog if obj["name"] in (
                "vw_fact_order_items",
                "vw_customer_summary",
                "vw_marketing_roas",
                "vw_carrier_performance",
                "commerceiq_customer_sessions_funnel",
                "commerceiq_inventory_snapshots",
                "commerceiq_customer_support_tickets",
                "olist_orders_dataset",
            )
        ]
        schema_str = json.dumps(views_only, indent=2)
        kpis_str = json.dumps(self.kpi_registry.get("kpis", []), indent=2)
        history_str = ""
        if chat_history:
            recent = chat_history[-4:]
            history_str = "\nRecent Conversation Context:\n" + "\n".join(
                [f"Q: {h.get('question', '')}\nSQL: {h.get('sql', '')}" for h in recent]
            )
        return (
            "You are a senior SQLite analytics engineer for the CommerceIQ e-commerce warehouse.\n"
            "Write ONE single read-only SQLite SELECT query to answer the user's business question.\n"
            "Rules:\n"
            "1. Output ONLY the raw SQL query inside a ```sql ... ``` block.\n"
            "2. Never use INSERT, UPDATE, DELETE, DROP, CREATE, PRAGMA, or multiple statements.\n"
            "3. Prefer the materialized analytical views (`vw_fact_order_items`, `vw_customer_summary`, "
            "`vw_marketing_roas`, `vw_carrier_performance`) whenever possible.\n"
            "4. Limit output to at most 50 rows.\n\n"
            f"Warehouse Schema Catalog:\n{schema_str}\n\n"
            f"KPI Registry Definitions:\n{kpis_str}\n"
            f"{history_str}\n\n"
            f"User Question: {question}\n"
        )

    def summarize_results(self, question: str, sql: str, df: pd.DataFrame, kpi: dict) -> str:
        if df.empty:
            return f"Executed query for '{question}' (`{kpi.get('name', 'KPI')}`), which returned 0 rows."

        preview_records = df.head(8).to_dict("records")
        llm_prompt = (
            f"You are an executive e-commerce analytics advisor. Summarize the database query result for the question:\n"
            f"Question: {question}\n"
            f"Target KPI: {kpi.get('name')} ({kpi.get('kpi_id')})\n"
            f"Executed SQL:\n{sql}\n"
            f"Query Result (top rows):\n{json.dumps(preview_records, indent=2)}\n\n"
            "Provide a concise 2-3 sentence business explanation citing exact numbers from the query result."
        )
        llm_summary = call_gemini_api(llm_prompt, api_key=self.api_key)
        if llm_summary:
            return llm_summary

        # Deterministic grounded summary
        top_row = df.iloc[0].to_dict()
        kv_pairs = ", ".join([f"{k}={v}" for k, v in list(top_row.items())[:5]])
        return (
            f"Grounded in `{kpi.get('name', 'Warehouse')}` ({len(df)} result rows returned): "
            f"leading record shows {kv_pairs}."
        )

    def ask(self, question: str, chat_history: list = None) -> dict:
        """
        Translates a plain-English question into validated SQL, executes it against
        the warehouse, and returns the SQL, validation audit, results, and explanation.
        """
        matched_kpi = self.match_kpi(question)
        prompt = self.build_llm_sql_prompt(question, chat_history=chat_history)
        raw_llm_sql = call_gemini_api(prompt, api_key=self.api_key)

        generation_mode = "gemini_llm"
        candidate_sql = self.extract_clean_sql(raw_llm_sql) if raw_llm_sql else ""
        validation = self.validate_sql(candidate_sql) if candidate_sql else {"is_valid": False, "reason": "LLM not invoked or no API key set."}

        if not validation["is_valid"]:
            fallback_sql, template_name = self.deterministic_fallback_sql(question)
            candidate_sql = fallback_sql
            generation_mode = f"deterministic_fallback ({template_name})"
            validation = self.validate_sql(candidate_sql)

        df = self.warehouse.query_df(candidate_sql)
        explanation = self.summarize_results(question, candidate_sql, df, matched_kpi)

        result_payload = {
            "question": question,
            "matched_kpi": {"kpi_id": matched_kpi.get("kpi_id"), "name": matched_kpi.get("name")},
            "generation_mode": generation_mode,
            "sql": candidate_sql,
            "validation": validation,
            "row_count": int(len(df)),
            "columns": list(df.columns),
            "records": df.head(50).to_dict("records"),
            "explanation": explanation,
        }
        return result_payload