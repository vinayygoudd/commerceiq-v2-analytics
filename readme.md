# CommerceIQ v2 — End-to-End 5-Pillar AI & E-Commerce Analytics Platform

An end-to-end e-commerce analytics, AI/ML intelligence, experimentation, and BI platform built on **9 untouched Olist Brazilian E-Commerce datasets** integrated with **9 validated synthetic v2 datasets** (`585,568` synthetic rows). CommerceIQ unifies an 18-table relational warehouse, automated data quality gates, Gemini-powered NL-to-SQL with read-only safeguards, Scikit-Learn customer churn/repeat-purchase models, Isolation Forest anomaly detection, AI executive insights, a 5-tab Streamlit conversational app, and a 4-page interactive BI dashboard suite (Tableau & Power BI).

> **Conversational AI App:** `streamlit run app_streamlit.py`

## Architecture Overview

CommerceIQ connects **five analytical pillars** plus an **AI/ML & Conversational Intelligence Layer** over a shared KPI registry (`config/kpi_registry.json`) and a materialized SQLite warehouse (`data/commerceiq_warehouse.db`):

| Pillar / Module | Scope | Key Components & Outputs |
| :--- | :--- | :--- |
| **1. Data Foundation** | 18-table relational warehouse & 4 materialized views | `src/commerceiq/db_engine.py` (vectorized Pandas hash merges), `vw_fact_order_items` (`112,650` rows), `vw_customer_summary` (`96,096` rows), `vw_marketing_roas` (`90` rows), `vw_carrier_performance` (`96,470` rows) |
| **2. Business Investigations & BI Marts** | Profitability waterfall, cohorts, funnel, logistics, inventory | `outputs/business_investigations_results.json`, 10 star-schema CSV marts in `bi/powerbi_star_schema/` |
| **3. Statistics & Experimentation** | Hypothesis testing & A/B experiment power sizing | `outputs/statistical_analytics_results.json` ($\chi^2$, t-tests, power analysis) |
| **4. AI & ML Intelligence** | NL-to-SQL, Churn/Repeat ML, Anomaly Detection & Insights | `src/commerceiq/ai/` (`orchestrator.py`, `nl_to_sql.py`, `insights_generator.py`), `src/commerceiq/ml/` (`customer_prediction.py`, `anomaly_detection.py`), `app_streamlit.py` |
| **5. Automation & BI Delivery** | Data quality gates, KPI alerts & dashboards | `outputs/automation_run_report.json`, `bi/dashboards/`, `bi/powerbi_dax_measures.dax`, 4-page Tableau dashboard |

## AI & Machine Learning Capabilities

1. **LLM-Based Natural Language to SQL (`src/commerceiq/ai/nl_to_sql.py`):**
   - Integrates **Google Gemini** (`GEMINI_API_KEY`) to translate plain-English business questions into SQLite queries grounded in `get_schema_catalog()` and `config/kpi_registry.json`.
   - Enforces strict **read-only SQL validation** (blocks `INSERT`/`UPDATE`/`DELETE`/`DROP`/`PRAGMA` and multi-statement injection, and validates schema/syntax via `EXPLAIN QUERY PLAN` before execution) with deterministic SQL templates as fallback.
2. **ML Customer Churn & Repeat-Purchase Prediction (`src/commerceiq/ml/customer_prediction.py`):**
   - Engineers behavioral, logistics, and channel features from `vw_customer_summary` (`96,096` customers; evaluated on `24,024` held-out test samples) using `scikit-learn` `RandomForestClassifier`.
   - **Repeat-Purchase Propensity Model:** `ROC-AUC = 0.7931`, `Recall = 0.8077` (`3.12%` positive rate).
   - **Customer Churn Risk Model:** `Precision = 0.9760`, `ROC-AUC = 0.6243`, `F1 = 0.3707`.
   - Exports customer risk segments (`High Churn Risk`, `Medium Churn Risk`, `High Repeat Propensity`, `Stable / Low Risk`) to `bi/powerbi_star_schema/mart_customer_risk_segments.csv`.
3. **Intelligent Anomaly Detection (`src/commerceiq/ml/anomaly_detection.py`):**
   - Runs `IsolationForest` + 6-week rolling z-scores across weekly GMV, order volume, AOV, and active customers.
   - Flagged **7 weekly anomalies** with quantified BRL impact and natural-language Gemini/grounded explanations (`outputs/anomaly_detection_results.json`, `bi/powerbi_star_schema/mart_anomaly_events.csv`).
4. **AI-Generated Business Insights (`src/commerceiq/ai/insights_generator.py`):**
   - Synthesizes YoY KPI movements, underperforming product categories, customer segment friction, and **3 evidence-backed recommendations** grounded in database results (`outputs/ai_executive_insights.md` & `.json`).
5. **Conversational Analytics Interface (`app_streamlit.py`):**
   - 5-tab Streamlit application supporting multi-turn follow-up questions (`st.session_state`), generated SQL & query-plan inspection, ML risk segment exploration, anomaly monitoring, and a live SQL guardrail tester.

## Data Quality & Validation Gate

Every pipeline run executes **49 automated validation checks** before building the warehouse (`outputs/validation_results_v2.json`):

* **Status:** `46 PASSED | 3 WARNINGS | 0 FAILED` (3 baseline Olist warnings: `775` orders without line items, `814` shared multi-order `review_id` rows, `2` untranslated categories).
* **Original Olist Preservation:** SHA-256 integrity verified across all 9 source Olist CSVs (`99,441` orders, `112,650` order items, `1,000,163` geolocation rows).
* **Structural Integrity:**
  * **Returns vs. Cancellations:** `7,616` post-delivery returns (`100%` delivered orders) strictly separated from `706` pre-shipment/order cancellations (`625` canceled orders).
  * **Shipment Eligibility:** `97,658` plausible shipments (excluding `1,783` unshipped/pre-ship canceled orders), with delivery timestamps restricted to `96,470` delivered orders.
  * **Multi-Session Journeys:** `145,458` sessions (`73,461` converting sessions, `43,701` multi-session customers, `6,631` zero-conversion customers).
  * **Inventory Flow Conservation:** 4 monthly snapshots (`2018-07-01` to `2018-10-01`, `137,792` rows) verified for inter-month stock continuity.

## Key KPIs & Automated Alerts

Snapshot from `outputs/automation_run_report.json` (`10` evaluated KPIs):

| KPI | Domain | Observed Value | Status / Alert |
| :--- | :--- | :---: | :--- |
| **Gross Merchandise Value (GMV)** | Revenue & Sales | `R$ 15,843,553.24` | Healthy |
| **Net Contribution Margin %** | Profitability & Pricing | `8.29%` | **HIGH Alert** (`< 15.0%` floor) |
| **Customer Repeat Purchase Rate %** | Customer Retention | `3.12%` | **MEDIUM Alert** (`< 3.5%` target) |
| **Session-to-Order Conversion %** | Acquisition & Funnel | `50.50%` | Healthy |
| **Paid Marketing ROAS** | Marketing Effectiveness | `6.37x` | Healthy |
| **Late Delivery Rate %** | Delivery & Logistics | `8.11%` | Healthy |
| **Post-Delivery Return Rate %** | Returns & Refunds | `6.91%` | Healthy |
| **Order Cancellation Rate %** | Cancellations & Refunds | `0.63%` | Healthy |
| **Monthly SKU-Seller Stockout Rate %** | Inventory & Supply Chain | `0.05%` | Healthy |
| **Support Ticket 48h SLA Breach Rate %** | Customer Experience | `11.76%` | Healthy |

## Highlighted Investigation: Why Did Repeat Purchases Decline?

Across `96,096` unique customers, the overall repeat purchase rate is **3.12%** (`2,997` repeat customers), dropping from **5.20%** in 2017-H1 cohorts (`740 / 14,239`) to **2.14%** in 2018 cohorts (`1,112 / 52,056`, $\chi^2 = 384.61, p = 1.23 \times 10^{-85}$).

1. **Observation Window Right-Censoring:** Repeat customers average **87.3 days** between first and final orders (`1,541` of `2,997` repeaters take `> 30` days), compressing observable repeats for 2018 cohorts before the October 2018 dataset cutoff.
2. **Logistics Delay Spike & Review Erosion:** Late delivery exposure rose from **4.78%** (2017-H1) to **9.32%** (2018), driving a **-1.72 star** review drop (`4.29` on-time vs. `2.57` late, $p < 10^{-100}$).
3. **Category Mix Shift:** Repeat retention varies over 2x across categories (`bed_bath_table` and `furniture_decor` lead repeat orders).
4. **Proposed Experiment (`EXP-01`):** 30-day post-delivery win-back voucher targeting a `+0.75%` absolute lift (`3.12% -> 3.87%`), sized at **6,841 customers per arm** (`13,682` total) at $\alpha = 0.05$ and `80%` power.

## BI Dashboard Suite (Tableau & Power BI)

The platform exports 10 star-schema marts in `bi/powerbi_star_schema/` powering a 4-page executive dashboard:

1. **Page 1 — Revenue & Unit Economics** (`mart_monthly_financials.csv`, `mart_category_unit_economics.csv`): Monthly GMV vs. Net Margin % trend, Top 15 categories by Net Contribution, and Return Rate vs. Margin scatter analysis.
2. **Page 2 — Retention & Funnel** (`mart_customer_cohorts.csv`, `mart_session_funnel.csv`, `mart_customer_risk_segments.csv`): Cohort repeat rate vs. late delivery trend, session-to-delivered funnel, LTV vs. CAC, and ML risk segments.
3. **Page 3 — Logistics & Inventory** (`mart_carrier_performance.csv`, `mart_inventory_snapshots.csv`): Carrier & service-tier late delivery rates, delivery variance vs. CSAT, and monthly stock flow (`closing_units` vs. `available_units`).
4. **Page 4 — Marketing & Support** (`mart_marketing_roas.csv`, `mart_support_sla_csat.csv`, `mart_anomaly_events.csv`): Channel ROAS vs. effective CAC, spend vs. attributed GMV, support 48h SLA breach rate vs. CSAT, and weekly anomaly events.

## Project Structure

```text
commerceiq_platform/
├── app_streamlit.py                 # 5-tab Conversational Analytics & AI/ML Streamlit UI
├── bi/
│   ├── dashboards/                  # 4 analytical dashboard PNGs
│   ├── powerbi_star_schema/         # 10 pre-aggregated mart_*.csv files (incl. ML & anomalies)
│   └── powerbi_dax_measures.dax     # Synchronized DAX KPI definitions
├── config/
│   └── kpi_registry.json            # Central KPI & alert threshold definitions
├── data/
│   └── commerceiq_warehouse.db      # Built 18-table SQLite warehouse + 4 views
├── docs/
│   └── diagrams/                    # Architecture & flywheel diagrams
├── logs/
│   └── automation_execution.log     # Pipeline execution audit log
├── outputs/
│   ├── ai_executive_insights.md
│   ├── ai_investigation_repeat_purchase_decline.md
│   ├── anomaly_detection_results.json
│   ├── automation_run_report.json
│   ├── business_investigations_results.json
│   ├── ml_customer_predictions_summary.json
│   ├── statistical_analytics_results.json
│   └── validation_results_v2.json
├── sql/
│   └── 02_analytical_views.sql
├── src/commerceiq/
│   ├── ai/
│   │   ├── orchestrator.py          # Deterministic 10-step root-cause orchestrator
│   │   ├── nl_to_sql.py             # Gemini NL-to-SQL engine + read-only guardrails
│   │   └── insights_generator.py    # AI executive business insights synthesizer
│   ├── ml/
│   │   ├── customer_prediction.py   # Scikit-Learn Churn & Repeat-Purchase models
│   │   └── anomaly_detection.py     # Isolation Forest + LLM anomaly explanations
│   └── db_engine.py                 # Vectorized Pandas + SQLite warehouse builder
└── run_commerceiq_platform.py       # End-to-end integrated pipeline runner
```

## Quick Start (Windows PowerShell)

```powershell
# 1. Set PYTHONPATH and optional Gemini API key
$env:PYTHONPATH="C:\Users\vinay\Downloads\commerceiq_app\commerceiq_platform\src;C:\Users\vinay\Downloads\commerceiq_app\commerceiq_platform\docs"
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

# 2. Run the full validation, warehouse, analytics, ML, AI & automation pipeline
python "C:\Users\vinay\Downloads\commerceiq_app\commerceiq_platform\run_commerceiq_platform.py"

# 3. Launch the Streamlit Conversational Analytics & AI/ML App
cd "C:\Users\vinay\Downloads\commerceiq_app\commerceiq_platform"
streamlit run app_streamlit.py
```

## Tech Stack

* **Data Engineering & Warehouse:** Python, Pandas, NumPy, SQLite
* **AI & Conversational Analytics:** Google Gemini API (`nl_to_sql.py`, `insights_generator.py`), Streamlit (`app_streamlit.py`)
* **Machine Learning & Anomaly Detection:** Scikit-Learn (`RandomForestClassifier`, `IsolationForest`), SciPy
* **BI & Visualization:** Tableau, Power BI (DAX & Star-Schema Marts), Matplotlib

**Author:** Dudala Vinay Kumar Goud