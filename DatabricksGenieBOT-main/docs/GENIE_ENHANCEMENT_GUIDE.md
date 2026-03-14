# Genie Enhancement Guide

Copy the sections below into your Genie space (Configure → Instructions) to enhance its capabilities.

---

## 1. TEXT INSTRUCTIONS (Configure → Instructions → Text)

Paste this into the **Text** tab:

```
## Role & Scope
You are an advanced Marketing Analytics Analyst. Your goal is to answer natural language questions with accurate SQL against the dev.`bet-allocato` schema. Always use backticks: dev.`bet-allocato`.table_name

## Tables & Columns Reference

**roi_channel_deepdive** – ROI, spend, pipeline
- Channel, region, GTM_segment
- Total_Spend, effective_Spend, driven_pipe
- Use driven_pipe for pipeline, Total_Spend for spend
- ROI formula: (driven_pipe / NULLIF(Total_Spend, 0)) * 100

**marginal_curve_spend** – Spend curves by region/channel
- region, channel, spend
- Key_2, Key_New
- Often multiple rows per region+channel (curve points) – use GROUP BY for summaries

**recommendation_table** – Pipeline, attribution, opportunities (use in generated SQL at runtime; do NOT add as SQL example – causes validation error)
- opp_stage, total_pipeline, influenced_pipeline, sourced_pipeline
- Channel, Region, Market Segment, Account Segment
- volume, marketing_sourced_pct, Quarter

**d_me_attribution** – Attribution touchpoints
**new_insights_1** – Insights and recommendations

## Query Patterns
- For "total" or "by channel/region": use GROUP BY and SUM()
- For "top N": use ROW_NUMBER() OVER (PARTITION BY x ORDER BY y) and filter rn <= N
- For "percent of total": use SUM(x) * 100.0 / SUM(SUM(x)) OVER (PARTITION BY y)
- For "max 50% change": use LEAST(recommended, current * 1.5)
- For ROI: compute (pipeline / spend) * 100 when no roi column exists
- Always use NULLIF(column, 0) when dividing to avoid divide-by-zero

## Response Format
1. Summary: 1–2 sentence insight
2. Data: Clean table with results
3. Next step: Suggest a follow-up question
```

---

## 2. SQL QUERY EXAMPLES (Configure → Instructions → SQL queries & functions)

Add each as a separate example. Use **+ Add** for each query.

### roi_channel_deepdive

```
Name: ROI by channel
SELECT Channel, Total_Spend, driven_pipe, ROUND((driven_pipe / NULLIF(Total_Spend, 0)) * 100, 2) AS roi_pct FROM dev.`bet-allocato`.roi_channel_deepdive ORDER BY roi_pct DESC
```

```
Name: Spend by region
SELECT region, Channel, SUM(Total_Spend) AS total_spend FROM dev.`bet-allocato`.roi_channel_deepdive GROUP BY region, Channel ORDER BY total_spend DESC
```

```
Name: Top channels by pipeline
SELECT Channel, SUM(driven_pipe) AS total_pipeline, SUM(Total_Spend) AS total_spend FROM dev.`bet-allocato`.roi_channel_deepdive GROUP BY Channel ORDER BY total_pipeline DESC LIMIT 10
```

```
Name: Capped spend 50%
SELECT Channel, Total_Spend, effective_Spend, LEAST(effective_Spend, Total_Spend * 1.5) AS capped_spend FROM dev.`bet-allocato`.roi_channel_deepdive ORDER BY driven_pipe DESC
```

```
Name: Pipeline percent of total
SELECT Channel, driven_pipe, ROUND(driven_pipe * 100.0 / SUM(driven_pipe) OVER (), 2) AS pct_of_total FROM dev.`bet-allocato`.roi_channel_deepdive ORDER BY driven_pipe DESC
```

```
Name: Top 5 per region
SELECT * FROM (SELECT region, Channel, SUM(Total_Spend) AS total_spend, ROW_NUMBER() OVER (PARTITION BY region ORDER BY SUM(Total_Spend) DESC) AS rn FROM dev.`bet-allocato`.roi_channel_deepdive GROUP BY region, Channel) WHERE rn <= 5 ORDER BY region, rn
```

### marginal_curve_spend

```
Name: Spend by region channel
SELECT region, channel, SUM(spend) AS total_spend FROM dev.`bet-allocato`.marginal_curve_spend GROUP BY region, channel ORDER BY total_spend DESC
```

```
Name: Top channels marginal
SELECT channel, SUM(spend) AS total_spend FROM dev.`bet-allocato`.marginal_curve_spend GROUP BY channel ORDER BY total_spend DESC LIMIT 10
```

### recommendation_table – DO NOT ADD AS SQL EXAMPLES

Genie's validator only sees columns from roi_channel_deepdive (Case, Channel, order, roi, Total budget). recommendation_table columns (opp_stage, total_pipeline) will cause BAD_REQUEST. Add this to **Text instructions** instead so Genie can generate these at runtime:

```
For pipeline by opp stage or channel, use: dev.`bet-allocato`.recommendation_table with columns opp_stage, total_pipeline, influenced_pipeline, Channel, Region. Example: SELECT opp_stage, SUM(total_pipeline) AS total_pipeline FROM dev.`bet-allocato`.recommendation_table GROUP BY opp_stage ORDER BY total_pipeline DESC
```

---

## 3. JOINS (Configure → Instructions → Joins)

If Genie supports explicit joins, define relationships:

| Left Table | Right Table | Join Key |
|------------|-------------|----------|
| roi_channel_deepdive | marginal_curve_spend | Channel = channel, region = region |
| recommendation_table | roi_channel_deepdive | Channel = Channel, Region = region |

---

## 4. DATA TAB CHECKLIST (Configure → Data)

- [ ] roi_channel_deepdive – first or primary (Genie validates SQL against this schema)
- [ ] marginal_curve_spend
- [ ] recommendation_table
- [ ] d_me_attribution
- [ ] new_insights_1

**Note:** Genie's SQL validator uses only the first/primary dataset's schema. recommendation_table columns (opp_stage, total_pipeline) will fail validation in SQL examples. Keep recommendation_table queries in Text instructions only.

---

## 5. QUICK REFERENCE – Column Mapping

| Question Type | Table | Key Columns |
|---------------|-------|--------------|
| ROI | roi_channel_deepdive | Channel, Total_Spend, driven_pipe |
| Spend optimization | roi_channel_deepdive | Total_Spend, effective_Spend |
| Spend curves | marginal_curve_spend | region, channel, spend |
| Pipeline | recommendation_table | opp_stage, total_pipeline, Channel |
| Attribution | d_me_attribution | (check schema) |
| Insights | new_insights_1 | (check schema) |

---

## 6. TEST QUESTIONS (for Genie space)

After applying, try:

1. What is the ROI by channel?
2. Show me spend by region
3. Top 5 channels by pipeline
4. What if I cap spend increase at 50%?
5. Pipeline by opportunity stage
6. Compare current vs recommended spend
