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

    # Find first string/category col and first numeric col
    label_idx = -1
    value_idx = -1
    for i, col in enumerate(columns):
        if _is_numeric_type(col.type_name):
            if value_idx < 0:
                value_idx = i
        else:
            if label_idx < 0:
                label_idx = i

    # Need at least one of each, or two numerics (use first as label if few rows)
    if label_idx >= 0 and value_idx >= 0 and label_idx != value_idx:
        pass
    elif value_idx >= 0 and len(columns) >= 2:
        # Try: first col as label, second as value
        if _is_numeric_type(columns[0].type_name) and _is_numeric_type(columns[1].type_name):
            label_idx = 0
            value_idx = 1
        elif not _is_numeric_type(columns[0].type_name) and _is_numeric_type(columns[1].type_name):
            label_idx = 0
            value_idx = 1
        else:
            return None
    else:
        return None

    labels: list[str] = []
    values: list[float] = []
    for row in data_array:
        v = _parse_value(row[value_idx], columns[value_idx])
        if v is not None:
            labels.append(str(row[label_idx]) if row[label_idx] is not None else "")
            values.append(v)

    if not labels or not values:
        return None

    # Limit for readability
    max_points = 15
    if len(labels) > max_points:
        labels = labels[:max_points]
        values = values[:max_points]

    return ChartData(
        labels=labels,
        values=values,
        chart_type=default_type,
        label_col=columns[label_idx].name,
        value_col=columns[value_idx].name,
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
        # bar (default)
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
                "plugins": {"legend": {"display": False}},
                "scales": {
                    "y": {"beginAtZero": True, "grid": {"color": "#e0e0e0"}},
                    "x": {"grid": {"display": False}},
                },
            },
        }

    json_str = json.dumps(config)
    encoded = urllib.parse.quote(json_str)
    return f"https://quickchart.io/chart?c={encoded}&backgroundColor=white&width=500&height=300"
