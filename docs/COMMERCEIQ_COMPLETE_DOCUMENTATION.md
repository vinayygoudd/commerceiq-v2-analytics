# CommerceIQ v2 — Complete 5-Pillar E-Commerce Intelligence Platform Documentation

## 1. System Architecture & Five-Pillar Integration

**CommerceIQ v2** is an end-to-end e-commerce analytics, experimentation, AI orchestration, and automation platform built on the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (`9` original CSV files, `1,550,882` rows preserved byte-for-byte unchanged) and extended with **9 validated CommerceIQ v2 synthetic tables** (`585,568` rows).

Rather than operating as disconnected scripts, all five pillars share a single relational warehouse (`18` tables + `4` analytical SQL views) and a single semantic KPI registry (`config/kpi_registry.json`):

1. **Pillar 1 — Data Analyst Foundation (`src/commerceiq/db_engine.py`, `sql/01_schema_postgresql.sql`, `sql/02_analytical_views.sql`):**
   * Integrates all `9` original Olist tables and `9` CommerceIQ v2 synthetic tables (`18` tables total) under both **PostgreSQL 15+** and an embedded **SQLite** analytical warehouse.
   * Enforces the `46` CommerceIQ v2 validation checks (`validate_commerceiq_dataset.py`), verifying SHA-256 preservation of original Olist files, `100%` foreign-key referential integrity, separation of post-delivery returns (`7,616` rows) from cancellations (`706` rows), plausible shipment gating (`97,658` rows), multi-session funnel behavior (`145,458` rows), and 4-period stock conservation (`137,792` rows).
   * Materializes four core analytical views: `vw_fact_order_items` (`112,650` rows), `vw_customer_summary` (`96,096` rows), `vw_marketing_roas` (`90` rows), and `vw_carrier_performance` (`96,470` delivered shipments).

2. **Pillar 2 — Business Analyst Engine (`src/commerceiq/analytics/business_investigations.py`, `sql/03_business_investigations.sql`):**
   * Executes 10 production SQL queries and Python domain investigations covering Revenue & Profitability Waterfalls, Cohort Retention, Acquisition & Funnel Conversion, Category Unit Economics, Marketing Channel ROAS, Returns vs. Cancellations, Carrier SLA Performance, Historical Inventory Movement, and Customer Support SLAs.
   * Exports 8 synchronized Power BI Star-Schema CSV marts (`bi/powerbi_star_schema/`) and 11 official DAX measures (`bi/powerbi_dax_measures.dax`).

3. **Pillar 3 — Statistics & Experimentation Framework (`src/commerceiq/statistics/experimentation.py`):**
   * Executes formal assumption checks (Shapiro-Wilk normality, Levene's variance homogeneity), parametric and non-parametric hypothesis tests (Welch's $t$-test, Mann-Whitney $U$, Chi-Square test of independence), $95\\%$ confidence intervals, effect sizes (Cohen's $d$, Cramér's $V$), multiple OLS regression (`numpy.linalg.lstsq` with exact $t$-statistics and $p$-values), and two-proportion Z-test A/B sample-size & power calculations.
   * Strictly separates **Observational Olist Findings** (`STAT-OBS-01` to `STAT-OBS-03`) from **Synthetic Assumption Audits** (`STAT-SYNTH-04`).

4. **Pillar 4 — AI-Augmented Analytics Orchestrator (`src/commerceiq/ai/orchestrator.py`):**
   * Parses natural-language business questions (such as *"Why did repeat purchases decline?"*), resolves the canonical KPI from `config/kpi_registry.json`, inspects warehouse schema metadata, generates and executes real SQL queries against the warehouse, runs SciPy statistical tests on the returned cohorts, and compiles an evidence-backed report (`outputs/ai_investigation_repeat_purchase_decline.md`) with zero fabricated calculations.

5. **Pillar 5 — Analytics Automation & Monitoring Engine (`src/commerceiq/automation/pipeline_runner.py`):**
   * Runs automated data-quality gate checks (`46 / 46` passed required before KPI refresh), evaluates all `10` canonical KPIs from `config/kpi_registry.json`, triggers severity-graded business threshold alerts (`HIGH`, `MEDIUM`, `LOW`), refreshes BI star-schema marts, and writes structured execution logs (`logs/automation_execution.log` and `outputs/automation_run_report.json`).

---

## 2. Unified KPI Dictionary (`config/kpi_registry.json`)

| KPI ID | KPI Name | Domain | Verified Value | Provenance | Alert Rule | Status |
| :--- | :--- | :--- | ---: | :--- | :--- | :--- |
| `gross_merchandise_value_brl` | Gross Merchandise Value (GMV) | Revenue & Sales | `R$ 15,843,553.24` | Original Olist (`order_items`) | None | Healthy |
| `net_contribution_margin_pct` | Net Contribution Margin % | Profitability & Pricing | `8.29%` (`R$ 1,314,071.10`) | Hybrid (Olist + Synthetic v2) | `< 15.0%` (`HIGH`) | **ALERT** |
| `repeat_purchase_rate_pct` | Customer Repeat Purchase Rate % | Customer Retention | `3.12%` (`2,997 / 96,096`) | Original Olist (`customers + orders`) | `< 3.50%` (`MEDIUM`) | **ALERT** |
| `session_to_order_conversion_pct` | Session-to-Order Placement % | Acquisition & Funnel | `50.50%` (`73,461 / 145,458`) | Synthetic v2 (`sessions_funnel`) | `< 45.0%` (`MEDIUM`) | Healthy |
| `paid_marketing_roas` | Paid Marketing ROAS | Marketing Effectiveness | `6.37x` | Hybrid (Olist LTV + Synthetic Spend) | `< 3.50x` (`HIGH`) | Healthy |
| `delivered_late_rate_pct` | Late Delivery Rate % (Delivered Only) | Delivery & Logistics | `8.11%` (`7,655 / 95,824`) | Original Olist Dates + Synthetic Carrier | `> 8.50%` (`HIGH`) | Healthy |
| `post_delivery_return_rate_pct` | Post-Delivery Item Return Rate % | Returns & Refunds | `6.91%` (`7,616` items) | Synthetic v2 (`returns_refunds`) | `> 8.00%` (`MEDIUM`) | Healthy |
| `order_cancellation_rate_pct` | Order Cancellation Rate % | Cancellations & Refunds | `0.63%` (`625 / 99,441`) | Original Olist (`orders`) | `> 1.00%` (`LOW`) | Healthy |
| `inventory_stockout_rate_pct` | Monthly SKU-Seller Stockout Rate % | Inventory & Supply Chain | `0.05%` (`69 / 137,792`) | Synthetic v2 (`inventory_snapshots`) | `> 0.50%` (`HIGH`) | Healthy |
| `support_sla_breach_rate_pct` | Support Ticket 48h SLA Breach % | Customer Experience | `11.76%` (`2,023 / 17,201`) | Synthetic v2 (`support_tickets`) | `> 15.0%` (`MEDIUM`) | Healthy |

---

## 3. Verified Business & Statistical Investigation Findings

### 3.1 Full Unit-Economics Profitability Waterfall (`vw_fact_order_items`)
Across `98,666` itemized orders (`112,650` line items):
* **Gross Merchandise Value (GMV):** `R$ 15,843,553.24` (`R$ 13,591,643.70` item selling price + `R$ 2,251,909.54` customer freight charged)
* **Less Brazilian ICMS Tax:** `-R$ 1,989,020.35`
* **Less Olist Marketplace Commission:** `-R$ 1,838,245.18`
* **Less Product Unit COGS:** `-R$ 7,316,445.64`
* **Less Packaging & Handling Cost:** `-R$ 234,175.03`
* **Less Actual Carrier Shipping Cost:** `-R$ 2,069,736.71`
* **Less Post-Delivery Return Refunds & Reverse Shipping:** `-R$ 844,184.56` refunds and `-R$ 131,319.91` reverse logistics (`7,616` returned delivered items)
* **Less Item Cancellation Refunds & Intercept Fees:** `-R$ 105,432.01` refunds and `-R$ 946.18` intercept fees
* **= Net Contribution Margin:** **`R$ 1,314,071.10` (`8.29%` of GMV)**

### 3.2 End-to-End AI & Statistical Investigation: *"Why Did Repeat Purchases Decline?"*
When a manager asks `"Why did repeat purchases decline?"`, `CommerceIQAIOrchestrator` executes a 10-step SQL + SciPy workflow:
1. **Cohort Trajectory (Observational Olist Fact):** Repeat purchase rate dropped from **5.20%** in `2017-H1` (`740 / 14,239` customers) to **3.84%** in `2017-H2` (`1,132 / 29,469`) and **2.14%** in `2018-H1/Q3` (`1,112 / 52,056`). A two-way Chi-Square test confirms $\\chi^2 = 384.61, p = 1.23 \\times 10^{-85}$.
2. **Primary Structural Driver — Observation Window Right-Censoring:** SQL window analysis on `olist_orders_dataset` proves repeat customers average **87.3 days** between their first and final order (`1,541` of `2,997` repeaters repurchase `> 30 days` later). Because the dataset closes in August–October 2018, 2018 cohorts had a truncated observation window.
3. **Operational Driver — Q1-2018 Late Delivery Surge:** Late-delivery exposure nearly doubled from **4.78%** in `2017-H1` to **9.32%** in `2018`. Across `95,824` delivered orders with reviews (`STAT-OBS-01`), late delivery causes a **-1.73 star drop** (`4.29` on-time vs. `2.57` late, 95% CI `[1.69, 1.77]`, Welch's $t = 89.43, p < 0.0001$, Cohen's $d = 1.45$). Multiple OLS regression (`STAT-OBS-03`, $R^2 = 0.1455$) confirms `is_late_delivery` ($\beta = -1.454, t = -81.02$) is the single largest negative driver of customer satisfaction.
4. **Actionable Experiment Design (`EXP-01`):** A 30-day post-delivery win-back voucher targeting a `+0.75%` absolute lift (`3.12% -> 3.87%`) at $\\alpha = 0.05$ and $80\\%$ statistical power requires **9,412 customers per arm** (`18,824` total).

---

## 4. Installation, Execution & Testing Instructions

### 4.1 Prerequisites
* Python `3.10+` with `pandas`, `numpy`, `scipy`, `matplotlib`, and `sqlite3` (all included in standard Anaconda / Google Colab environments).
* Optional for production server deployment: PostgreSQL `15+` (`sql/01_schema_postgresql.sql`).

### 4.2 One-Command Execution (All 5 Pillars)
```bash
# Execute all 5 pillars, build warehouse, export Power BI marts, and generate reports & dashboards:
python3 run_commerceiq_platform.py

# Run the end-to-end 5-pillar integration test suite:
python3 tests/test_end_to_end_integration.py
```

### 4.3 Connecting Power BI Desktop
1. Open **Power BI Desktop** -> **Get Data** -> **Folder / Text/CSV** and point to `bi/powerbi_star_schema/` (or connect directly to PostgreSQL / SQLite `vw_fact_order_items`, `vw_customer_summary`, `vw_marketing_roas`, and `vw_carrier_performance`).
2. Paste the official DAX definitions from `bi/powerbi_dax_measures.dax` into your Power BI Measure table.
3. Open `bi/dashboards/commerceiq_executive_dashboard.html` in any browser for an immediate zero-dependency executive view.
