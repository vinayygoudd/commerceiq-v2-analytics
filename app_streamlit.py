#!/usr/bin/env python3
"""
CommerceIQ — Capability 5: Conversational Analytics & AI/ML Suite (Streamlit)
=============================================================================
Interactive Streamlit application providing:
1. Conversational NL-to-SQL Assistant (with follow-up context, SQL validation,
   query plan inspection, KPI mapping, and result tables)
2. ML Customer Churn & Repeat-Purchase Prediction Explorer
3. Intelligent Anomaly Detection Monitor (Isolation Forest + LLM Explanations)
4. AI-Generated Executive Business Insights & Recommendations
5. Read-Only SQL Sandbox Validator

Launch locally from `commerceiq_platform/`:
    streamlit run app_streamlit.py
"""

import os
import sys
import json
import pandas as pd
import streamlit as st

PLATFORM_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PLATFORM_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from commerceiq.db_engine import CommerceIQWarehouse
from commerceiq.ai.nl_to_sql import CommerceIQNLToSQL
from commerceiq.ai.insights_generator import CommerceIQInsightsGenerator
from commerceiq.ml.customer_prediction import CommerceIQCustomerPrediction
from commerceiq.ml.anomaly_detection import CommerceIQAnomalyDetector


def get_warehouse() -> CommerceIQWarehouse:
    olist_dir = os.environ.get("COMMERCEIQ_OLIST_DIR", r"C:\Users\vinay\Downloads\archive (5)")
    synth_dir = os.environ.get("COMMERCEIQ_SYNTH_DIR", r"C:\Users\vinay\Downloads\commerceiq_v2\synthetic_commerceiq")
    db_path = os.path.join(PLATFORM_ROOT, "data", "commerceiq_warehouse.db")
    return CommerceIQWarehouse(PLATFORM_ROOT, olist_dir, synth_dir, db_path=db_path)


def main():
    st.set_page_config(page_title="CommerceIQ v2 — AI & Conversational Analytics", layout="wide")
    st.title("CommerceIQ v2 — Conversational Analytics & AI/ML Intelligence")
    st.caption(
        "Grounded in the 18-Table Olist + Synthetic v2 Relational Warehouse (`commerceiq_warehouse.db`) "
        "and `config/kpi_registry.json`"
    )

    with st.sidebar:
        st.header("AI & Warehouse Controls")
        api_key_input = st.text_input(
            "Gemini API Key (optional — falls back to deterministic SQL/synthesis if blank)",
            value=os.environ.get("GEMINI_API_KEY", ""),
            type="password",
        )
        if api_key_input:
            os.environ["GEMINI_API_KEY"] = api_key_input

        st.markdown("**Quick Sample Questions:**")
        sample_questions = [
            "Which product categories have the lowest net contribution margin %?",
            "How did repeat purchase rate and late delivery change across 2017 and 2018 cohorts?",
            "Which carriers and service tiers have the highest late delivery percentage?",
            "What is the ROAS and effective CAC for each marketing channel?",
            "Show the monthly GMV, order count, and net margin trend.",
        ]
        selected_sample = st.selectbox("Select a question to pre-fill:", [""] + sample_questions)

        if st.button("Clear Conversation Context"):
            st.session_state["chat_history"] = []
            st.rerun()

    wh = get_warehouse()
    outputs_dir = os.path.join(PLATFORM_ROOT, "outputs")
    bi_mart_dir = os.path.join(PLATFORM_ROOT, "bi", "powerbi_star_schema")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Conversational NL-to-SQL",
        "2. ML Customer Predictions",
        "3. Anomaly Detection",
        "4. AI Executive Insights",
        "5. SQL Guardrail Validator",
    ])

    with tab1:
        st.subheader("Ask Business Questions in Plain English")
        nl_engine = CommerceIQNLToSQL(wh, output_dir=outputs_dir, api_key=api_key_input or None)

        for idx, turn in enumerate(st.session_state["chat_history"]):
            with st.chat_message("user"):
                st.markdown(f"**{turn['question']}**")
            with st.chat_message("assistant"):
                st.markdown(turn["explanation"])
                c1, c2, c3 = st.columns(3)
                c1.metric("Matched KPI", turn["matched_kpi"].get("name", "N/A"))
                c2.metric("Engine Mode", turn["generation_mode"])
                c3.metric("Rows Returned", f"{turn['row_count']:,}")
                with st.expander(f"View Validated SQL & Execution Safeguards (Turn #{idx + 1})", expanded=False):
                    st.code(turn["sql"], language="sql")
                    st.json(turn["validation"])
                if turn["records"]:
                    st.dataframe(pd.DataFrame(turn["records"]), use_container_width=True)

        user_q = st.chat_input("Ask a question or follow-up about revenue, margins, cohorts, carriers, or ROAS...")
        if not user_q and selected_sample and st.button("Run Selected Sample Question"):
            user_q = selected_sample

        if user_q:
            with st.spinner("Generating, validating, and executing SQL against commerceiq_warehouse.db..."):
                resp = nl_engine.ask(user_q, chat_history=st.session_state["chat_history"])
                st.session_state["chat_history"].append(resp)
                st.rerun()

    with tab2:
        st.subheader("ML Customer Churn & Repeat-Purchase Prediction (`vw_customer_summary`)")
        ml_json_path = os.path.join(outputs_dir, "ml_customer_predictions_summary.json")
        if st.button("Train / Refresh Scikit-Learn Customer Models") or not os.path.exists(ml_json_path):
            with st.spinner("Training Churn & Repeat-Purchase RandomForest models on 96,096 customers..."):
                ml_runner = CommerceIQCustomerPrediction(wh, output_dir=outputs_dir, bi_mart_dir=bi_mart_dir)
                ml_data = ml_runner.run_prediction_pipeline()
        else:
            with open(ml_json_path, "r", encoding="utf-8") as f:
                ml_data = json.load(f)

        cm = ml_data["churn_model_evaluation"]
        rm = ml_data["repeat_purchase_model_evaluation"]
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Customer Churn Risk Model")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Precision", f"{cm['precision']:.3f}")
            m2.metric("Recall", f"{cm['recall']:.3f}")
            m3.metric("F1-Score", f"{cm['f1_score']:.3f}")
            m4.metric("ROC-AUC", f"{cm['roc_auc']:.3f}")
            st.json(ml_data["top_churn_drivers"])
        with col_b:
            st.markdown("#### Repeat-Purchase Propensity Model")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Precision", f"{rm['precision']:.3f}")
            r2.metric("Recall", f"{rm['recall']:.3f}")
            r3.metric("F1-Score", f"{rm['f1_score']:.3f}")
            r4.metric("ROC-AUC", f"{rm['roc_auc']:.3f}")
            st.json(ml_data["top_repeat_purchase_drivers"])

        st.markdown("#### Customer Risk Segments (Exported to `mart_customer_risk_segments.csv`)")
        st.dataframe(pd.DataFrame(ml_data["risk_segment_summary"]), use_container_width=True)

    with tab3:
        st.subheader("Intelligent Anomaly Detection (Isolation Forest + Rolling Z-Score)")
        anom_json_path = os.path.join(outputs_dir, "anomaly_detection_results.json")
        if st.button("Run Anomaly Detection Scan") or not os.path.exists(anom_json_path):
            with st.spinner("Running IsolationForest & quantifying BRL business impact..."):
                detector = CommerceIQAnomalyDetector(wh, output_dir=outputs_dir, bi_mart_dir=bi_mart_dir, api_key=api_key_input or None)
                anom_data = detector.detect_anomalies()
        else:
            with open(anom_json_path, "r", encoding="utf-8") as f:
                anom_data = json.load(f)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Periods Analyzed", f"{anom_data['total_periods_analyzed']}")
        k2.metric("Anomalies Detected", f"{anom_data['anomalies_detected_count']}")
        k3.metric("Positive Surge Impact", f"R$ {anom_data['quantified_business_impact']['positive_surge_gmv_delta_brl']:,.2f}")
        k4.metric("Negative Drop Impact", f"R$ {anom_data['quantified_business_impact']['negative_drop_gmv_delta_brl']:,.2f}")

        st.markdown("#### Natural-Language Anomaly Explanation")
        st.markdown(anom_data["natural_language_explanation"])
        st.markdown("#### Detected Anomaly Records (`mart_anomaly_events.csv`)")
        st.dataframe(pd.DataFrame(anom_data["detected_anomalies"]), use_container_width=True)

    with tab4:
        st.subheader("AI-Generated Executive Business Insights")
        ins_json_path = os.path.join(outputs_dir, "ai_executive_insights.json")
        if st.button("Regenerate Executive Insights") or not os.path.exists(ins_json_path):
            with st.spinner("Querying warehouse views & synthesizing executive insights..."):
                ins_gen = CommerceIQInsightsGenerator(wh, output_dir=outputs_dir, api_key=api_key_input or None)
                ins_data = ins_gen.generate_executive_insights()
        else:
            with open(ins_json_path, "r", encoding="utf-8") as f:
                ins_data = json.load(f)

        st.markdown(ins_data["executive_narrative"])
        st.markdown("#### Underperforming Categories (Lowest Net Contribution Margin %)")
        st.dataframe(pd.DataFrame(ins_data["underperforming_categories"]), use_container_width=True)
        st.markdown("#### Evidence-Backed Recommendations")
        st.dataframe(pd.DataFrame(ins_data["evidence_backed_recommendations"]), use_container_width=True)

    with tab5:
        st.subheader("Read-Only SQL Validation & Execution Safeguard Tester")
        custom_sql = st.text_area(
            "Enter a SQL query to test CommerceIQ's read-only guardrails (`SELECT` allowed; `DROP`/`DELETE`/`UPDATE` blocked):",
            value="SELECT product_category_english, COUNT(*) AS units, ROUND(SUM(net_contribution_brl), 2) AS net_contrib FROM vw_fact_order_items GROUP BY 1 ORDER BY 3 DESC LIMIT 10;",
            height=120,
        )
        if st.button("Validate & Execute SQL"):
            nl_engine = CommerceIQNLToSQL(wh, output_dir=outputs_dir)
            val = nl_engine.validate_sql(custom_sql)
            if val["is_valid"]:
                st.success(val["reason"])
                st.json(val)
                df_custom = wh.query_df(custom_sql)
                st.dataframe(df_custom, use_container_width=True)
            else:
                st.error(f"Execution Blocked by Guardrail: {val['reason']}")


if __name__ == "__main__":
    main()