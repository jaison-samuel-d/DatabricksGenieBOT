"""
Chart generation from tabular data using QuickChart.io.
Uses professional palette: #4e79a7 (Blue), #f28e2b (Orange), #e15759 (Red).
"""
import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

from databricks.sdk.service.sql import ColumnInfo, ColumnInfoTypeName

# Log
logger = logging.getLogger(__name__)

# Professional palette - extend for many categories
CHART_COLORS = [
    "#4e79a7",  # Blue
    "#f28e2b",  # Orange
    "#e15759",  # Red
    "#76b7b2",  # Teal
    "#59a14f",  # Green
    "#edc948",  # Yellow
    "#b07aa1",  # Purple
    "#ff9da7",  # Pink
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
                        "borderWidth": 2,
                    }
                ],
            },
            "options": {
                "plugins": {
                    "legend": {"position": "right", "labels": {"font": {"size": 12}}},
                    "datalabels": {"display": True, "color": "#333"},
                },
                "layout": {"padding": 20},
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
                        "borderColor": "#4e79a7",
                        "backgroundColor": "rgba(78, 121, 167, 0.1)",
                        "fill": True,
                        "tension": 0.3,
                        "pointBackgroundColor": "#4e79a7",
                        "pointRadius": 4,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {"legend": {"display": False}},
                "scales": {
                    "y": {"beginAtZero": True, "grid": {"color": "#e0e0e0"}},
                    "x": {"grid": {"display": False}},
                },
            },
        }
    else:
        # bar (default) - with data labels on bars
        config = {
            "type": "bar",
            "data": {
                "labels": chart_data.labels,
                "datasets": [
                    {
                        "label": chart_data.value_col,
                        "data": chart_data.values,
                        "backgroundColor": colors,
                        "borderColor": "#ffffff",
                        "borderWidth": 1,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "legend": {"display": False},
                    "datalabels": {
                        "display": True,
                        "anchor": "end",
                        "align": "top",
                        "color": "#333",
                        "font": {"size": 10, "weight": "bold"},
                    },
                },
                "scales": {
                    "y": {"beginAtZero": True, "grid": {"color": "#e0e0e0"}},
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

    if len(labels) == 1:
        return f"• {labels[0]}: {values[0]:,.2f} ({value_col})"

    # Top performer
    top_idx = max(range(len(values)), key=lambda i: values[i])
    top_label = labels[top_idx]
    top_val = values[top_idx]

    # Bottom performer
    bot_idx = min(range(len(values)), key=lambda i: values[i])
    bot_label = labels[bot_idx]
    bot_val = values[bot_idx]

    lines = [f"• Top: {top_label} leads with {top_val:,.2f} ({value_col})"]

    if len(labels) >= 2 and bot_val and bot_val > 0:
        ratio = top_val / bot_val
        lines.append(f"• {top_label} is {ratio:.1f}x higher than {bot_label} ({bot_val:,.2f})")

    if len(labels) >= 2:
        total = sum(values)
        pct = (top_val / total * 100) if total else 0
        lines.append(f"• {top_label} represents {pct:.0f}% of total")

    return "\n\n".join(lines)
