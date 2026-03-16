"""
Chart generation from tabular data.
Uses QuickChart.io by default (reliable in Azure). Vega-Lite when CHART_BASE_URL + CHART_USE_VEGA are set.
"""
import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

from databricks.sdk.service.sql import ColumnInfo, ColumnInfoTypeName

from chatx.const import CHART_BASE_URL, CHART_USE_VEGA, CHART_WIDTH, CHART_HEIGHT, CHART_PIE_SIZE

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
    Build chart URL. When CHART_BASE_URL and CHART_USE_VEGA are set, uses Vega-Lite
    (requires --workers 1 in gunicorn). Otherwise uses QuickChart.io (reliable in Azure).
    """
    if CHART_BASE_URL and CHART_USE_VEGA:
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
        return f"https://quickchart.io/chart?c={encoded}&backgroundColor=white&width={CHART_WIDTH}&height={CHART_HEIGHT}"

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
    # Larger dimensions for Teams full-width display (max 1200px per Teams)
    w, h = (1200, 600) if chart_data.chart_type == "pie" else (1200, 550)
    return f"https://quickchart.io/chart?c={encoded}&backgroundColor=white&width={w}&height={h}"


def generate_chart_insights(chart_data: ChartData) -> str:
    """Generate a single flowing paragraph that explains the chart (Genie-style)."""
    if not chart_data or not chart_data.labels:
        return ""
    labels = chart_data.labels
    n = len(labels)

    def _fmt(v: float) -> str:
        if abs(v) >= 1e9:
            return f"{v/1e9:.2f}B"
        if abs(v) >= 1e6:
            return f"{v/1e6:.2f}M"
        if abs(v) >= 1e3:
            return f"{v/1e3:.2f}K"
        return f"{v:,.2f}"

    # Multi-series (e.g. Previous vs Recommended Spend + % Change) - Genie-style paragraph
    if chart_data.datasets and len(chart_data.datasets) >= 2:
        series_names = [d["label"] for d in chart_data.datasets]
        intro = (
            f"The data shows {', '.join(series_names)} for each {chart_data.label_col.lower()}. "
        )
        segs: list[str] = []
        for i, lbl in enumerate(labels):
            vals = [d["values"][i] if i < len(d["values"]) else 0 for d in chart_data.datasets]
            parts: list[str] = []
            for name, v in zip(series_names, vals):
                name_lower = name.lower()
                if "pct" in name_lower or "percent" in name_lower or "change" in name_lower:
                    direction = "an increase" if v >= 0 else "a decrease"
                    parts.append(f"{name} of {abs(v):,.1f}% ({direction})")
                else:
                    parts.append(f"{name} was {_fmt(v)}")
            segs.append(f"{lbl}: {', '.join(parts)}")
        body = " ".join(segs) + ". "
        # Add concluding insight
        pct_series = [
            d for d in chart_data.datasets
            if "pct" in d["label"].lower() or "change" in d["label"].lower()
        ]
        if pct_series and labels:
            max_idx = max(
                range(n),
                key=lambda i: pct_series[0]["values"][i] if i < len(pct_series[0]["values"]) else 0,
            )
            min_idx = min(
                range(n),
                key=lambda i: pct_series[0]["values"][i] if i < len(pct_series[0]["values"]) else 0,
            )
            if max_idx != min_idx:
                body += (
                    f"{labels[max_idx]} has the largest recommended increase, "
                    f"while {labels[min_idx]} shows a decrease. "
                )
        return intro + body

    values = chart_data.values
    if not values:
        return ""
    value_col = chart_data.value_col
    label_col = chart_data.label_col

    if n == 1:
        return (
            f"The chart shows {label_col} with a single value: {labels[0]} at "
            f"{_fmt(values[0])} ({value_col})."
        )

    total = sum(values)
    sorted_pairs = sorted(zip(values, labels), key=lambda x: x[0], reverse=True)
    top_val, top_label = sorted_pairs[0]
    bot_val, bot_label = sorted_pairs[-1]

    intro = f"The data shows {value_col} across {n} {label_col.lower()}. "
    body_parts: list[str] = []
    for v, lbl in sorted_pairs:
        pct = (v / total * 100) if total else 0
        body_parts.append(f"{lbl} has {_fmt(v)} ({pct:.0f}% of the total)")
    body = ", ".join(body_parts) + ". "
    if n >= 2 and bot_val and bot_val > 0:
        ratio = top_val / bot_val
        body += f"{top_label} leads and is {ratio:.1f}x higher than {bot_label}. "
    if chart_data.chart_type == "line" and n >= 2:
        first_val, first_label = values[0], labels[0]
        last_val, last_label = values[-1], labels[-1]
        if first_val and first_val != 0:
            pct_change = ((last_val - first_val) / first_val) * 100
            direction = "up" if pct_change > 0 else "down"
            body += f"Trend is {direction} {abs(pct_change):.1f}% from {first_label} to {last_label}."
    return intro + body


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
