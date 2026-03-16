"""
Chart generation from tabular data using QuickChart.io.
Uses vibrant, colourful palette for engaging visualizations.
"""
import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

from databricks.sdk.service.sql import ColumnInfo, ColumnInfoTypeName

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


def build_chart_data(
    columns: list[ColumnInfo],
    data_array: list[list[Any]],
    question_hint: str = "",
) -> ChartData | None:
    """
    Detect chartable data: one label column (string/category) + one numeric column.
    Returns ChartData or None if not chartable.
    """
    if not columns or not data_array:
        return None

    # Prefer bar for comparisons, line for trends, pie for composition
    q = (question_hint or "").lower()
    default_type = "bar"
    if "trend" in q or "over time" in q or "by month" in q or "by quarter" in q:
        default_type = "line"
    elif "share" in q or "composition" in q or "breakdown" in q or "pie" in q:
        default_type = "pie"

    # Find dimension cols (string/category) and value col (numeric)
    dim_idxs: list[int] = []
    value_idx = -1
    for i, col in enumerate(columns):
        if _is_numeric_type(col.type_name):
            if value_idx < 0:
                value_idx = i
        else:
            dim_idxs.append(i)

    # Need at least one dimension and one numeric
    if not dim_idxs or value_idx < 0:
        if value_idx >= 0 and len(columns) >= 2 and not _is_numeric_type(columns[0].type_name):
            dim_idxs = [0]
            value_idx = 1
        else:
            return None

    # Use most granular dimension: last dim col, or combine if multiple (e.g. region + channel)
    labels: list[str] = []
    values: list[float] = []
    for row in data_array:
        v = _parse_value(row[value_idx], columns[value_idx])
        if v is not None:
            parts = [
                str(row[i]) if row[i] is not None else ""
                for i in dim_idxs
            ]
            label = " – ".join(p for p in parts if p) or "—"
            labels.append(label)
            values.append(round(v, 2))  # Round to 2 decimals for cleaner chart

    if not labels or not values:
        return None

    # Limit for readability
    max_points = 15
    if len(labels) > max_points:
        labels = labels[:max_points]
        values = values[:max_points]

    label_col = " – ".join(columns[i].name for i in dim_idxs)
    value_col_raw = columns[value_idx].name
    value_col_display = _format_chart_label(value_col_raw)
    return ChartData(
        labels=labels,
        values=values,
        chart_type=default_type,
        label_col=label_col,
        value_col=value_col_display,
    )


def get_chart_url(chart_data: ChartData) -> str:
    """Build QuickChart.io URL with custom colors and style."""
    colors = CHART_COLORS * ((len(chart_data.labels) // len(CHART_COLORS)) + 1)
    colors = colors[: len(chart_data.labels)]

    if chart_data.chart_type == "pie":
        config = {
            "type": "pie",
            "data": {
                "labels": chart_data.labels,
                "datasets": [
                    {
                        "data": chart_data.values,
                        "backgroundColor": colors,
                        "borderColor": "#ffffff",
                        "borderWidth": 3,
                        "hoverOffset": 12,
                    }
                ],
            },
            "options": {
                "plugins": {
                    "legend": {"position": "right", "labels": {"font": {"size": 12, "weight": "bold"}}},
                    "datalabels": {"display": True, "color": "#1a1a1a", "font": {"size": 11, "weight": "bold"}},
                },
                "layout": {"padding": 24},
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
    return f"https://quickchart.io/chart?c={encoded}&backgroundColor=white&width=900&height=500"


def generate_chart_insights(chart_data: ChartData) -> str:
    """Generate human-readable insights from chart data."""
    if not chart_data or not chart_data.labels or not chart_data.values:
        return ""
    labels = chart_data.labels
    values = chart_data.values
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

    if chart_data and chart_data.labels and chart_data.values:
        sorted_pairs = sorted(
            zip(chart_data.values, chart_data.labels),
            key=lambda x: x[0],
            reverse=True,
        )
        top_val, top_label = sorted_pairs[0]

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
