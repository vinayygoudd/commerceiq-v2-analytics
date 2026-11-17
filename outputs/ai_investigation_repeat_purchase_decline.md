# CommerceIQ AI-Assisted Investigation Report: Why Did Repeat Purchases Decline?

**Identified KPI:** `repeat_purchase_rate_pct` (Customer Repeat Purchase Rate %) — *Original Olist (customers + orders)*
**Source Views Queried:** `olist_customers_dataset, olist_orders_dataset, vw_carrier_performance, vw_customer_summary, vw_fact_order_items`

## 1. Executive Summary of Verified Findings
Across the entire Olist marketplace (`96,096` unique customers), the overall repeat purchase rate is **3.12%** (`2,997` repeat customers). Cohort decomposition reveals that acquisition cohorts from **2017-H1** achieved a **5.20%** repeat rate (`740` / `14,239`), whereas **2018** cohorts dropped to **2.14%** (`1,112` / `52,056`). A Chi-Square test confirms this drop is highly statistically significant ($\chi^2 = 384.61, p = 1.23e-85$).

## 2. Three Verified Root Causes (SQL + Statistical Evidence)
1. **Observation Window Right-Censoring (Primary Structural Driver):** SQL inter-purchase interval analysis (`olist_orders_dataset`) shows that repeat customers take an average of **87.3 days** between their first and final order (`1,541` of `2,997` repeaters take `> 30 days`). Because the dataset ends in October 2018, 2018 cohorts had a compressed post-acquisition window.
2. **Q1-2018 Logistics Delay Spike & Review Score Erosion:** Late delivery exposure increased from **4.78%** in 2017-H1 to **9.32%** in 2018, driving a `-1.72` star drop on late orders (`4.29` vs. `2.57` stars, $p < 10^{-100}$).
3. **Category Mix Shift:** Repeat rates vary more than 2x across categories (`bed_bath_table` and `furniture_decor` lead repeat retention, while high-ticket durable categories expanded in 2018).

## 3. Recommended Experiment & Automated Monitoring
* **A/B Test Design (`EXP-01`):** Launch a 30-day post-delivery win-back voucher targeting a `+0.75%` absolute lift in repeat conversion (`3.12% -> 3.87%`). At $\alpha = 0.05$ (two-sided) and $80\%$ statistical power, the experiment requires **6,841 customers per arm** (`13,682` total).
* **Automated Alert Rule Activated:** Pillar 5 monitors `repeat_purchase_rate_pct < 3.5%` (`MEDIUM` severity).
