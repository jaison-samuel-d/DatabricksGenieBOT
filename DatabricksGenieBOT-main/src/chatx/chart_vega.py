"""
Genie-style charts using Vega-Lite (Databricks' native visualization format).
Renders to PNG via vl-convert for Teams Adaptive Cards.
"""
import hashlib
import json
import logging
from typing import Any

from chatx.chart_builder import ChartData

# Log
logger = logging.getLogger(__name__)

# Genie-style color palette (Databricks blue/teal, orange, green)
GENIE_COLORS = [
    "#1E88E5",  # Databricks blue
    "#FF9800",  # Orange
    "#43A047",  # Green
    "#5E35B1",  # Purple
    "#E53935",  # Red
]


def _chart_data_to_long(chart_data: ChartData) -> list[dict]:
    """Convert ChartData to long format for Vega-Lite."""
    rows: list[dict] = []
    labels = chart_data.labels
    if chart_data.datasets:
        for i, label in enumerate(labels):
            for ds in chart_data.datasets:
                vals = ds.get("values", [])
                if i < len(vals):
                    rows.append({
                        "category": label,
                        "series": ds["label"],
                        "value": vals[i],
                        "yAxis": ds.get("yAxisID", "y0"),
                    })
    else:
        for i, label in enumerate(labels):
            if i < len(chart_data.values):
                rows.append({
                    "category": label,
                    "series": chart_data.value_col or "Value",
                    "value": chart_data.values[i],
                    "yAxis": "y0",
                })
    return rows


def build_vega_spec(chart_data: ChartData) -> dict:
    """
    Build Vega-Lite spec matching Genie's chart style.
    Supports grouped bar with optional dual Y-axis.
    """
    data = _chart_data_to_long(chart_data)
    if not data:
        return {}

    has_dual = chart_data.datasets and any(
        d.get("yAxisID") == "y1" for d in chart_data.datasets
    )

    # Color scale: map series to Genie palette
    series_names = list({r["series"] for r in data})
    color_range = GENIE_COLORS[: len(series_names)]

    if has_dual:
        # Split into left-axis (y0) and right-axis (y1) layers
        left_data = [r for r in data if r["yAxis"] == "y0"]
        right_data = [r for r in data if r["yAxis"] == "y1"]
        if not left_data or not right_data:
            has_dual = False

    if has_dual and chart_data.datasets:
        left_data = [r for r in data if r["yAxis"] == "y0"]
        right_data = [r for r in data if r["yAxis"] == "y1"]
        left_series = list({r["series"] for r in left_data})
        right_series = list({r["series"] for r in right_data})
        left_colors = [GENIE_COLORS[i] for i in range(len(left_series))]
        right_colors = [GENIE_COLORS[len(left_series) + i] for i in range(len(right_series))] if right_series else [GENIE_COLORS[len(left_series)]]

        # Layer 1: Left-axis grouped bars (spend/revenue)
        layer_left = {
            "mark": {"type": "bar", "cornerRadius": 4},
            "encoding": {
                "x": {"field": "category", "type": "nominal", "axis": {"labelAngle": -45}},
                "y": {
                    "field": "value",
                    "type": "quantitative",
                    "axis": {"title": "(USD)", "format": "~s", "grid": True},
                    "scale": {"domain": [0, None]},
                },
                "xOffset": {"field": "series"},
                "color": {
                    "field": "series",
                    "scale": {"range": left_colors},
                    "legend": {"title": None},
                },
            },
            "transform": [{"filter": {"field": "yAxis", "equal": "y0"}}],
        }

        # Layer 2: Right-axis bars (% change) - single or grouped
        layer_right = {
            "mark": {"type": "bar", "cornerRadius": 4, "opacity": 0.9},
            "encoding": {
                "x": {"field": "category", "type": "nominal"},
                "y": {
                    "field": "value",
                    "type": "quantitative",
                    "axis": {"title": "% Change", "format": ".1f", "grid": False},
                    "scale": {"domain": [None, None]},
                },
                "color": {
                    "field": "series",
                    "scale": {"range": right_colors},
                    "legend": {"title": None},
                },
            },
            "transform": [{"filter": {"field": "yAxis", "equal": "y1"}}],
        }
        if len(right_series) > 1:
            layer_right["encoding"]["xOffset"] = {"field": "series"}

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": 900,
            "height": 480,
            "title": {
                "text": f"{chart_data.label_col} – {' vs '.join(series_names[:4])}",
                "fontSize": 14,
            },
            "data": {"values": data},
            "layer": [layer_left, layer_right],
            "resolve": {"scale": {"y": "independent"}},
            "config": {
                "axis": {"labelFontSize": 11, "titleFontSize": 11},
                "legend": {"labelFontSize": 11},
            },
        }
    elif chart_data.datasets and len(chart_data.datasets) >= 2:
        # Grouped bar, single axis
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": 900,
            "height": 480,
            "title": {
                "text": f"{chart_data.label_col} – {' vs '.join(series_names[:4])}",
                "fontSize": 14,
            },
            "data": {"values": data},
            "mark": {"type": "bar", "cornerRadius": 4},
            "encoding": {
                "x": {"field": "category", "type": "nominal", "axis": {"labelAngle": -45}},
                "y": {
                    "field": "value",
                    "type": "quantitative",
                    "axis": {"format": "~s", "grid": True},
                    "scale": {"domain": [0, None]},
                },
                "xOffset": {"field": "series"},
                "color": {
                    "field": "series",
                    "scale": {"range": color_range},
                    "legend": {"title": None},
                },
            },
            "config": {
                "axis": {"labelFontSize": 11, "titleFontSize": 11},
                "legend": {"labelFontSize": 11},
            },
        }
    elif chart_data.chart_type == "line":
        # Line chart
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": 900,
            "height": 480,
            "data": {"values": data},
            "mark": {"type": "line", "point": True, "strokeWidth": 2},
            "encoding": {
                "x": {"field": "category", "type": "nominal"},
                "y": {"field": "value", "type": "quantitative", "scale": {"domain": [0, None]}},
                "color": {"field": "series", "scale": {"range": color_range}},
            },
            "config": {"axis": {"labelFontSize": 11}},
        }
    elif chart_data.chart_type == "pie":
        # Pie chart - use first series only
        first_series = series_names[0] if series_names else None
        pie_data = [
            {"category": r["category"], "value": r["value"]}
            for r in data
            if r["value"] > 0 and (first_series is None or r["series"] == first_series)
        ]
        if not pie_data:
            pie_data = [{"category": "—", "value": 1}]
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": 500,
            "height": 500,
            "data": {"values": pie_data},
            "mark": {"type": "arc", "innerRadius": 0},
            "encoding": {
                "theta": {"field": "value", "type": "quantitative"},
                "color": {
                    "field": "category",
                    "scale": {"range": GENIE_COLORS},
                    "legend": {"orient": "right"},
                },
            },
            "config": {"legend": {"labelFontSize": 11}},
        }
    else:
        # Single bar
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": 900,
            "height": 480,
            "data": {"values": data},
            "mark": {"type": "bar", "cornerRadius": 4},
            "encoding": {
                "x": {"field": "category", "type": "nominal", "axis": {"labelAngle": -45}},
                "y": {"field": "value", "type": "quantitative", "scale": {"domain": [0, None]}},
                "color": {"value": GENIE_COLORS[0]},
            },
            "config": {"axis": {"labelFontSize": 11}},
        }

    return spec


def render_chart_png(chart_data: ChartData) -> bytes:
    """Render ChartData to PNG using Vega-Lite + vl-convert."""
    try:
        import vl_convert as vlc
    except ImportError:
        logger.warning("vl-convert not installed, cannot render Vega-Lite charts")
        return b""

    spec = build_vega_spec(chart_data)
    if not spec:
        return b""

    try:
        png_data = vlc.vegalite_to_png(vl_spec=json.dumps(spec), scale=2)
        return png_data
    except Exception as e:
        logger.error(f"Vega-Lite render failed: {e}")
        return b""


def chart_cache_key(chart_data: ChartData) -> str:
    """Generate cache key for chart data."""
    data = {
        "labels": chart_data.labels,
        "values": chart_data.values,
        "type": chart_data.chart_type,
        "datasets": chart_data.datasets,
    }
    h = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return h[:16]
