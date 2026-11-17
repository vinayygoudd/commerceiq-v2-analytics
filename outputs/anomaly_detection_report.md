# CommerceIQ — Intelligent Anomaly Detection Report

**Detection Engine:** `Scikit-Learn IsolationForest + 6-Week Rolling Z-Score` | **Explanation Mode:** `deterministic_grounded_explanation`
**Periods Analyzed:** `87` | **Anomalies Flagged:** `7`

## 1. Quantified Business Impact
- **Positive Surge GMV Delta vs. Rolling Baseline:** `R$ 379,428.89`
- **Negative Drop GMV Delta vs. Rolling Baseline:** `R$ -219,362.07`

## 2. AI Natural-Language Explanation of Top Anomalies
- **2017-W47 (2017-11-20) — Revenue & Order Surge (Peak Event / Black Friday):** GMV reached R$ 474,623.65 (+R$ 243,892.80 vs. rolling baseline, z=2.02), with 2,979 orders, 2,938 active customers, and R$ 159.32 AOV.
- **2017-W01 (2017-01-05) — Multivariate Activity Anomaly:** GMV reached R$ 3,953.17 (+R$ 0.00 vs. rolling baseline, z=0.00), with 46 orders, 31 active customers, and R$ 85.94 AOV.
- **2018-W35 (2018-08-27) — Revenue & Volume Drop:** GMV reached R$ 11,995.53 (R$ -219,362.07 vs. rolling baseline, z=-1.73), with 116 orders, 116 active customers, and R$ 103.41 AOV.
- **2017-W02 (2017-01-09) — Multivariate Activity Anomaly:** GMV reached R$ 14,742.33 (+R$ 5,394.58 vs. rolling baseline, z=0.71), with 79 orders, 77 active customers, and R$ 186.61 AOV.
- **2017-W03 (2017-01-16) — Multivariate Activity Anomaly:** GMV reached R$ 28,318.24 (+R$ 12,646.99 vs. rolling baseline, z=1.04), with 195 orders, 189 active customers, and R$ 145.22 AOV.
