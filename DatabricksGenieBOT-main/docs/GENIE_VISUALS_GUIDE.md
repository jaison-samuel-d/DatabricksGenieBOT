# Why Visuals Don't Show in Teams & How to Fix

## Root Cause

**The Genie Conversation API returns tabular data only** — not chart images or visualization metadata.

| Where | What you see |
|-------|--------------|
| **Databricks Genie UI** | Charts, tables, rich text — rendered client-side by the Genie web app |
| **Genie API** | `statement_response` with `data_array` (rows/columns) — raw query results |
| **Teams bot** | Tables (Adaptive Card) or plain text — we render what the API gives us |

The Databricks Genie UI builds charts from the same tabular data. The API does not expose chart images or visualization URLs, so the bot only receives tables.

---

## What You Can Do

### 1. Genie Space Instructions (Standalone Spaces)

If your Genie space is **standalone** (not auto-generated from a dashboard), you can edit instructions to steer responses:

**Where:** Databricks → Genie → Your Space → Configure → **Instructions** tab

**Example instructions to add:**

```
When the user asks for comparisons, trends, breakdowns, or "show me" style questions:
- Prefer returning aggregated data with clear column names (e.g. category, region, value)
- Use one dimension column and one or more measure columns when possible
- This helps downstream tools render the data as charts
```

This does **not** change the API format (still tables), but it can improve how data is structured for future chart rendering.

---

### 2. Use a Dashboard-Backed Genie Space

Genie spaces created from **published dashboards** have built-in chart context:

- Databricks auto-generates a Genie space when you publish a dashboard with **Enable Genie** on
- The space knows about your dashboard datasets and visualizations
- Genie can answer questions like "Show me sales by product line" with better context

**How to use:**

1. Publish a dashboard with **Enable Genie** enabled
2. Open the dashboard → **Open Genie Space** (kebab menu)
3. Copy the space ID from the URL (or use the Genie API to list spaces)
4. Update `spaces.json` to point the bot to this space

**Note:** You cannot edit instructions for auto-generated dashboard spaces from the UI.

---

### 3. Prompt Phrasing

Ask explicitly for chart-style answers:

- ❌ "Give me Facebook ROI"
- ✅ "Show me a bar chart of Facebook ROI by region"
- ✅ "Compare ROI by region and quarter as a chart"

Genie may still return a table, but the structure (e.g. region + value columns) will be better suited for charting.

---

### 4. Bot-Side Chart Generation (Future)

To show charts in Teams, the bot would need to:

1. Detect when query results are chartable (e.g. 2 columns: category + numeric)
2. Generate a chart image (e.g. via [QuickChart.io](https://quickchart.io/) or similar)
3. Send the image in the Teams message

This is not implemented yet. If you want this, we can add it.

---

## Summary

| Action | Effect |
|--------|--------|
| Edit Genie space instructions | Better-structured tabular data (for standalone spaces) |
| Use dashboard-backed Genie space | Richer context; Genie understands your charts |
| Phrase prompts for charts | More chart-friendly result structure |
| Add chart generation to bot | Actual chart images in Teams (requires code change) |

The main limitation is **API design**: the Genie API returns raw query results, not visualizations. The Databricks UI renders charts itself; the bot would need to do the same from the tabular data.
