"""
Chart generation from tabular data.
Uses Vega-Lite (Genie-style) when CHART_BASE_URL is set, else QuickChart.io.
"""
import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

from databricks.sdk.service.sql import ColumnInfo, ColumnInfoTypeName

from chatx.const import CHART_BASE_URL

# Log
logger = logging.getLogger(__name__)

# Vibrant, colourful palette for charts
CHART_COLORS = [
    "#FF6B6B",  # Coral red
    "#4ECDC4",  # Turquoise
    "#45B7D1",  # Sky blue
    "#96CEB4",  # Sage green
    "#FFEAA7",  # Soft yellow
    "#DDA0DD",  # Plum
    "#98D8C8",  # Mint
    "#F7DC6F",  # Amber
    "#BB8FCE",  # Lavender
    "#85C1E9",  # Light blue
]


@dataclass
class ChartData:
    """Parsed chart-ready data from a table row."""

    labels: list[str]
    values: list[float]
    chart_type: str  # bar, line, pie
    label_col: str
    value_col: str
    # Multi-series grouped bar (like Genie): list of {label, values, yAxisID?}
    datasets: list[dict] | None = None


def _format_chart_label(col_name: str) -> str:
    """Convert column names to human-readable chart labels."""
    if not col_name:
        return col_name
    name = col_name.lstrip("_").replace("_", " ").strip()
    labels = {
        "roi percentage": "ROI (%)",
        "roi": "ROI (%)",
        "total spend": "Total Spend",
        "total pipeline": "Total Pipeline",
        "avg spend": "Avg Spend",
        "avg pipeline": "Avg Pipeline",
        "driven pipe": "Driven Pipeline",
    }
    return labels.get(name.lower(), name.title())


def _is_numeric_type(type_name: ColumnInfoTypeName | None) -> bool:
    if not type_name:
        return False
    return type_name in [
        ColumnInfoTypeName.DECIMAL,
        ColumnInfoTypeName.DOUBLE,
        ColumnInfoTypeName.FLOAT,
        ColumnInfoTypeName.INT,
        ColumnInfoTypeName.LONG,
        ColumnInfoTypeName.SHORT,
    ]


def _parse_value(val: Any, col: ColumnInfo) -> float | None:
    if val is None:
        return None
    try:
        if col.type_name in [
            ColumnInfoTypeName.DECIMAL,
            ColumnInfoTypeName.DOUBLE,
            ColumnInfoTypeName.FLOAT,
        ]:
            return float(val)
        if col.type_name in [
            ColumnInfoTypeName.INT,
            ColumnInfoTypeName.LONG,
            ColumnInfoTypeName.SHORT,
        ]:
            return float(int(val))
        return float(val)
    except (ValueError, TypeError):
        return None


def _infer_chart_type_from_data(
    labels: list[str],
    values: list[float],
    label_col: str,
    value_col_raw: str,
    question_hint: str,
) -> str:
    """
    Infer best chart type from data shape and column names.
    Returns 'pie', 'line', or 'bar'.
    """
    q = (question_hint or "").lower()
    label_lower = label_col.lower()
    value_lower = value_col_raw.lower()
    n = len(labels)
    total = sum(values) if values else 0

    # Line: time/sequence dimension (month, quarter, year, date, week)
    time_keywords = ("month", "quarter", "year", "date", "week", "period", "day")
    if any(kw in label_lower for kw in time_keywords):
        return "line"
    if any(kw in q for kw in ("trend", "over time", "by month", "by quarter")):
        return "line"

    # Pie: composition data - few categories (2-8), percentage-like values or column
    is_pct_col = any(kw in value_lower for kw in ("percent", "pct", "share", "composition"))
    values_sum_to_100 = total > 0 and 99 <= total <= 101
    few_categories = 2 <= n <= 8

    if few_categories and (is_pct_col or values_sum_to_100):
        return "pie"
    if few_categories and any(kw in q for kw in ("share", "composition", "breakdown", "pie", "pie chart")):
        return "pie"

    # Bar: default for comparisons
    return "bar"


def _is_pct_change_column(col_name: str) -> bool:
    """True if column looks like % change (different scale from spend/revenue)."""
    n = col_name.lower()
    return any(kw in n for kw in ("pct_change", "percent_change", "% change", "pct change"))


def build_chart_data(
    columns: list[ColumnInfo],
    data_array: list[list[Any]],
    question_hint: str = "",
) -> ChartData | None:
    """
    Detect chartable data. Prefers multi-series grouped bar (like Genie) when
    we have 1 dimension + 2+ numeric columns. Otherwise single label + value.
    """
    if not columns or not data_array:
        return None

    # Find dimension cols and all numeric cols
    dim_idxs: list[int] = []
    value_idxs: list[int] = []
    for i, col in enumerate(columns):
        if _is_numeric_type(col.type_name):
            value_idxs.append(i)
        else:
            dim_idxs.append(i)

    if not dim_idxs:
        if value_idxs and len(columns) >= 2 and not _is_numeric_type(columns[0].type_name):
            dim_idxs = [0]
        else:
            return None

    # Build labels from dimension(s)
    labels: list[str] = []
    for row in data_array:
        parts = [str(row[i]) if row[i] is not None else "" for i in dim_idxs]
        label = " – ".join(p for p in parts if p) or "—"
        labels.append(label)

    max_points = 15
    if len(labels) > max_points:
        labels = labels[:max_points]
        data_array = data_array[:max_points]

    label_col = " – ".join(columns[i].name for i in dim_idxs)

    # Multi-series grouped bar (Genie-style): 1 dim + 2–5 numeric cols
    if len(value_idxs) >= 2 and len(value_idxs) <= 5 and 2 <= len(labels) <= 12:
        datasets_list: list[dict] = []
        for vi in value_idxs:
            col = columns[vi]
            vals: list[float] = []
            for row in data_array:
                v = _parse_value(row[vi], col)
                vals.append(round(v, 2) if v is not None else 0)
            col_label = col.name.replace("_", " ")
            y_axis = "y1" if _is_pct_change_column(col.name) else "y0"
            datasets_list.append({"label": col_label, "values": vals, "yAxisID": y_axis})
        return ChartData(
            labels=labels,
            values=[],  # unused for multi-series
            chart_type="bar",
            label_col=label_col,
            value_col="",
            datasets=datasets_list,
        )

    # Single-series fallback
    value_idx = value_idxs[0] if value_idxs else -1
    if value_idx < 0:
        return None

    values: list[float] = []
    for row in data_array:
        v = _parse_value(row[value_idx], columns[value_idx])
        if v is not None:
            values.append(round(v, 2))
        else:
            values.append(0)
    if not any(v != 0 for v in values):
        return None

    value_col_raw = columns[value_idx].name
    value_col_display = _format_chart_label(value_col_raw)
    chart_type = _infer_chart_type_from_data(
        labels, values, label_col, value_col_raw, question_hint
    )
    return ChartData(
        labels=labels,
        values=values,
        chart_type=chart_type,
        label_col=label_col,
        value_col=value_col_display,
    )


def get_chart_url(chart_data: ChartData) -> str:
    """
    Build chart URL. When CHART_BASE_URL is set, uses Vega-Lite (Genie-style)
    and serves from our /api/chart endpoint. Otherwise uses QuickChart.io.
    """
    if CHART_BASE_URL:
        try:
            from chatx.chart_vega import chart_cache_key, render_chart_png
            from chatx.chart_cache import store_chart

            png_data = render_chart_png(chart_data)
            if png_data:
                key = chart_cache_key(chart_data)
                store_chart(key, png_data)
                return f"{CHART_BASE_URL}/api/chart/{key}"
        except Exception as e:
            logger.warning("Vega-Lite chart failed, falling back to QuickChart: %s", e)

    # QuickChart.io fallback
    return _get_quickchart_url(chart_data)


def _get_quickchart_url(chart_data: ChartData) -> str:
    """Build QuickChart.io URL with custom colors and style."""
    # Multi-series grouped bar (Genie-style: Previous vs Recommended + % Change)
    if chart_data.datasets and len(chart_data.datasets) >= 2:
        has_y1 = any(d.get("yAxisID") == "y1" for d in chart_data.datasets)
        datasets_config = []
        for i, ds in enumerate(chart_data.datasets):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            d = {
                "label": ds["label"],
                "data": ds["values"],
                "backgroundColor": color,
                "borderColor": color,
                "borderWidth": 1,
            }
            if ds.get("yAxisID") == "y1":
                d["yAxisID"] = "y1"
            datasets_config.append(d)

        scales: dict = {
            "xAxes": [{"gridLines": {"display": False}, "ticks": {"maxRotation": 45}}],
        }
        if has_y1:
            scales["yAxes"] = [
                {"id": "y0", "position": "left", "ticks": {"beginAtZero": True}, "scaleLabel": {"display": True, "labelString": "(USD)"}},
                {"id": "y1", "position": "right", "ticks": {"beginAtZero": True}, "scaleLabel": {"display": True, "labelString": "% Change"}},
            ]
        else:
            scales["yAxes"] = [{"ticks": {"beginAtZero": True}}]

        chart_title = ""
        if chart_data.label_col and chart_data.datasets:
            series = " vs ".join(d["label"] for d in chart_data.datasets[:3])
            chart_title = f"{chart_data.label_col} - {series}"
        config = {
            "type": "bar",
            "data": {
                "labels": chart_data.labels,
                "datasets": datasets_config,
            },
            "options": {
                "responsive": True,
                "legend": {"display": True, "position": "top"},
                "title": {"display": bool(chart_title), "text": chart_title or "Chart"},
                "scales": scales,
            },
        }
        json_str = json.dumps(config)
        encoded = urllib.parse.quote(json_str)
        return f"https://quickchart.io/chart?c={encoded}&backgroundColor=white&width=1000&height=500"

    colors = CHART_COLORS * ((len(chart_data.labels) // len(CHART_COLORS)) + 1)
    colors = colors[: len(chart_data.labels)]

    if chart_data.chart_type == "pie":
        # Use abbreviated values and display:'auto' to prevent overlapping labels
        config = {
            "type": "pie",
            "data": {
                "labels": chart_data.labels,
                "datasets": [
                    {
                        "data": chart_data.values,
                        "backgroundColor": colors,
                        "borderColor": "#ffffff",
                        "borderWidth": 2,
                        "hoverOffset": 8,
                    }
                ],
            },
            "options": {
                "plugins": {
                    "legend": {"position": "right", "labels": {"font": {"size": 11}}},
                    "datalabels": {
                        "display": "auto",
                        "color": "#1a1a1a",
                        "font": {"size": 9},
                        "anchor": "end",
                        "align": "start",
                        "offset": 6,
                        "padding": 4,
                    },
                },
                "layout": {"padding": 32},
            },
        }
    elif chart_data.chart_type == "line":
        config = {
            "type": "line",
            "data": {
                "labels": chart_data.labels,
                "datasets": [
                    {
                        "label": chart_data.value_col,
                        "data": chart_data.values,
                        "borderColor": "#4ECDC4",
                        "backgroundColor": "rgba(78, 205, 196, 0.25)",
                        "fill": True,
                        "tension": 0.4,
                        "pointBackgroundColor": "#4ECDC4",
                        "pointBorderColor": "#2C7A7B",
                        "pointBorderWidth": 2,
                        "pointRadius": 5,
                        "pointHoverRadius": 8,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {"legend": {"display": False}},
                "scales": {
                    "y": {"beginAtZero": True, "grid": {"color": "#e8e8e8"}},
                    "x": {"grid": {"display": False}},
                },
            },
        }
    else:
        # bar (default) - vibrant multi-color bars
        config = {
            "type": "bar",
            "data": {
                "labels": chart_data.labels,
                "datasets": [
                    {
                        "label": "",
                        "data": chart_data.values,
                        "backgroundColor": colors,
                        "borderColor": "#ffffff",
                        "borderWidth": 2,
                        "borderRadius": 4,
                        "borderSkipped": False,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "legend": {"display": False},
                "plugins": {
                    "legend": {"display": False},
                    "datalabels": {
                        "display": True,
                        "anchor": "end",
                        "align": "top",
                        "color": "#1a1a1a",
                        "font": {"size": 11, "weight": "bold"},
                    },
                },
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "grid": {"color": "#e8e8e8"},
                        "title": {"display": True, "text": chart_data.value_col},
                    },
                    "x": {
                        "grid": {"display": False},
                        "ticks": {"maxRotation": 45, "minRotation": 0},
                    },
                },
            },
        }

    json_str = json.dumps(config)
    encoded = urllib.parse.quote(json_str)
    # Use larger dimensions for pie charts to reduce label overlap
    w, h = (1000, 600) if chart_data.chart_type == "pie" else (900, 500)
    return f"https://quickchart.io/chart?c={encoded}&backgroundColor=white&width={w}&height={h}"


def generate_chart_insights(chart_data: ChartData) -> str:
    """Generate human-readable insights from chart data."""
    if not chart_data or not chart_data.labels:
        return ""
    labels = chart_data.labels
    values = chart_data.values
    if not values and chart_data.datasets:
        # Use first dataset for insights
        values = chart_data.datasets[0].get("values", [])
    if not values:
        return ""
    value_col = chart_data.value_col
    label_col = chart_data.label_col
    n = len(values)

    if n == 1:
        return f"• {labels[0]}: {values[0]:,.2f} ({value_col})"

    total = sum(values)
    avg = total / n if n else 0
    sorted_pairs = sorted(zip(values, labels), key=lambda x: x[0], reverse=True)

    # Top performer
    top_val, top_label = sorted_pairs[0]
    bot_val, bot_label = sorted_pairs[-1]

    lines: list[str] = []

    # Lead insight
    lines.append(f"• **Top performer:** {top_label} leads with {top_val:,.2f} ({value_col})")

    # Share of total
    pct_top = (top_val / total * 100) if total else 0
    lines.append(f"• **Share of total:** {top_label} represents {pct_top:.0f}% of the total ({total:,.2f})")

    # Second and third place (if available)
    if n >= 2:
        second_val, second_label = sorted_pairs[1]
        pct_second = (second_val / total * 100) if total else 0
        lines.append(f"• **Second:** {second_label} at {second_val:,.2f} ({pct_second:.0f}% of total)")
    if n >= 3:
        third_val, third_label = sorted_pairs[2]
        pct_third = (third_val / total * 100) if total else 0
        lines.append(f"• **Third:** {third_label} at {third_val:,.2f} ({pct_third:.0f}% of total)")

    # Top vs bottom comparison
    if n >= 2 and bot_val and bot_val > 0:
        ratio = top_val / bot_val
        lines.append(f"• **Spread:** {top_label} is {ratio:.1f}x higher than {bot_label} ({bot_val:,.2f})")

    # Average and distribution
    above_avg = sum(1 for v in values if v > avg)
    below_avg = sum(1 for v in values if v < avg)
    lines.append(f"• **Average:** {avg:,.2f} — {above_avg} items above average, {below_avg} below")

    # Range
    val_range = top_val - bot_val if n >= 2 else 0
    lines.append(f"• **Range:** {bot_val:,.2f} to {top_val:,.2f} (span of {val_range:,.2f})")

    # Trend (first vs last - useful for time series)
    if n >= 2 and chart_data.chart_type == "line":
        first_val, first_label = values[0], labels[0]
        last_val, last_label = values[-1], labels[-1]
        if first_val and first_val != 0:
            pct_change = ((last_val - first_val) / first_val) * 100
            direction = "up" if pct_change > 0 else "down"
            lines.append(
                f"• **Trend:** {direction} {abs(pct_change):.1f}% from {first_label} ({first_val:,.2f}) "
                f"to {last_label} ({last_val:,.2f})"
            )

    # Bottom performer context
    if n >= 2:
        pct_bot = (bot_val / total * 100) if total else 0
        lines.append(f"• **Lowest:** {bot_label} at {bot_val:,.2f} ({pct_bot:.0f}% of total)")

    return "\n\n".join(lines)


def generate_followup_questions(
    chart_data: "ChartData | None",
    chart_insights: str,
    genie_answer: str,
    question: str,
) -> list[str]:
    """
    Generate 2-3 contextual follow-up questions from chart data and insights.
    Returns list of suggested questions for the user to click.
    """
    followups: list[str] = []
    q_lower = (question or "").lower()

    vals = chart_data.values if chart_data.values else (
        chart_data.datasets[0]["values"] if chart_data.datasets else []
    )
    if chart_data and chart_data.labels and vals:
        sorted_pairs = sorted(
            zip(vals, chart_data.labels),
            key=lambda x: x[0],
            reverse=True,
        )
        top_val, top_label = sorted_pairs[0] if sorted_pairs else (0, "")

        # "Drill into [top performer]"
        if top_label and len(top_label) < 50:
            followups.append(f"Drill into {top_label}")

        # "Compare [top] with [second]" if we have 2+
        if len(sorted_pairs) >= 2:
            _, second_label = sorted_pairs[1]
            if second_label and len(second_label) < 50:
                followups.append(f"Compare {top_label} with {second_label}")

        # "Show trend for [top]" for time-series style questions
        if any(w in q_lower for w in ["trend", "over time", "by month", "by quarter"]):
            followups.append(f"Show trend for {top_label}")

    # "Breakdown by region" / "Breakdown by channel" from question
    if "roi" in q_lower or "spend" in q_lower:
        if "region" not in q_lower and "channel" in q_lower:
            followups.append("Breakdown by region")
        elif "channel" not in q_lower and "region" in q_lower:
            followups.append("Breakdown by channel")

    # "Compare regions" / "Compare channels"
    if "channel" in q_lower:
        followups.append("Compare pipeline across regions")
    if "region" in q_lower:
        followups.append("Compare channels by spend")

    # Dedupe and limit to 3
    seen: set[str] = set()
    unique: list[str] = []
    for f in followups:
        f_clean = f.strip()
        if f_clean and f_clean not in seen:
            seen.add(f_clean)
            unique.append(f_clean)
            if len(unique) >= 3:
                break

    return unique
