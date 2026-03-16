import re
from dataclasses import dataclass
import logging

from databricks.sdk.service.sql import StatementResponse, ColumnInfoTypeName
from databricks.sdk.service.dashboards import GenieResultMetadata
from botbuilder.schema import Activity, ActivityTypes

from chatx.adaptive_card import AdaptiveCardFactory
from chatx.chart_builder import (
    build_chart_data,
    get_chart_url,
    generate_chart_insights,
    generate_followup_questions,
)

# Log
logger = logging.getLogger(__name__)

def _get_column_display_name(col_name: str) -> str:
    """Return display name for table header - use Genie's column names as-is."""
    return col_name.replace("_", " ")

# Phrase to strip from Genie summaries (e.g. "You want to see X" -> "X")
_SUMMARY_PREFIX_TO_STRIP = "you want to see "


def _clean_summary_text(text: str) -> str:
    """Rewrite 'You want to see X' style summaries to direct 'X'."""
    if not text or len(text) < 20:
        return text
    t = text.strip()
    if t.lower().startswith(_SUMMARY_PREFIX_TO_STRIP):
        rest = t[len(_SUMMARY_PREFIX_TO_STRIP):].strip()
        if rest:
            return rest[0].upper() + rest[1:] if len(rest) > 1 else rest.upper()
    return text


def _to_single_paragraph(text: str) -> str:
    """
    Convert Genie text to a single flowing paragraph (no separate headings).
    Strips markdown headers, replaces 'Analysis' with 'Summary', collapses newlines.
    """
    if not text or not text.strip():
        return text
    t = text.strip()
    # Replace "Analysis" heading/label with "Summary"
    t = re.sub(r"\bAnalysis\b", "Summary", t, flags=re.IGNORECASE)
    # Strip markdown headers (##, ###, ####) - keep the content after them
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)
    # Collapse multiple newlines/spaces into single space
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _fix_summary_count_mismatch(summary: str, actual_row_count: int) -> str:
    """Fix 'top N' in summary when it doesn't match actual row count (e.g. top 10 but 8 rows)."""
    if not summary or actual_row_count <= 0:
        return summary
    match = re.search(r"\btop\s+(\d+)\b", summary, re.IGNORECASE)
    if match:
        stated_n = int(match.group(1))
        if stated_n != actual_row_count:
            summary = re.sub(
                r"\btop\s+" + str(stated_n) + r"\b",
                f"top {actual_row_count}",
                summary,
                flags=re.IGNORECASE,
            )
    return summary


# Short/affirmative replies that are user echo, not real summaries
_USER_ECHO_PATTERNS = frozenset({
    "yes", "no", "ok", "okay", "sure", "please", "thanks", "thank you",
    "y", "n", "yep", "nope", "yeah", "nah", "maybe", "continue", "go",
})


def _is_user_echo(genie_answer: str, question: str) -> bool:
    """True if genie_answer is just echoing the user's input, not a real summary."""
    if not genie_answer or len(genie_answer) > 200:
        return False
    a = genie_answer.strip().lower()
    q = (question or "").strip().lower()
    if a in _USER_ECHO_PATTERNS:
        return True
    if q and a == q:
        return True
    if q and len(a) < 50 and q in a:
        return True
    return False


def _generate_summary_from_data(
    columns: list, data_array: list[list], question: str = ""
) -> str:
    """Generate a short summary from the data when Genie doesn't provide one."""
    if not data_array or not columns:
        return ""
    row = data_array[0]
    parts: list[str] = []
    n_rows = len(data_array)
    for i, col in enumerate(columns):
        if i >= len(row):
            break
        val = row[i]
        if val is None:
            continue
        name = col.name.lower().replace("_", " ")
        try:
            if col.type_name in [
                ColumnInfoTypeName.DECIMAL,
                ColumnInfoTypeName.DOUBLE,
                ColumnInfoTypeName.FLOAT,
            ]:
                f = float(val)
                if f >= 1e9:
                    parts.append(f"{name}: {f/1e9:.2f}B")
                elif f >= 1e6:
                    parts.append(f"{name}: {f/1e6:.2f}M")
                elif f >= 1e3:
                    parts.append(f"{name}: {f/1e3:.2f}K")
                else:
                    parts.append(f"{name}: {f:,.2f}")
            elif col.type_name in [
                ColumnInfoTypeName.INT,
                ColumnInfoTypeName.LONG,
                ColumnInfoTypeName.SHORT,
            ]:
                n = int(val)
                if abs(n) >= 1e9:
                    parts.append(f"{name}: {n/1e9:.2f}B")
                elif abs(n) >= 1e6:
                    parts.append(f"{name}: {n/1e6:.2f}M")
                else:
                    parts.append(f"{name}: {n:,}")
            else:
                parts.append(f"{name}: {val}")
        except (ValueError, TypeError):
            parts.append(f"{name}: {val}")
    if not parts:
        return ""
    summary = " | ".join(parts[:5])
    if n_rows > 1:
        summary = f"Breakdown across {n_rows} items. Top result: {summary}"
    return summary


@dataclass
class GenieResult:
    query_description: str | None = None
    query: str | None = None
    query_result_metadata: GenieResultMetadata | None = None
    statement_id: str | None = None
    statement_response: StatementResponse | None = None
    message: str | None = None
    conversation_id: str | None = None
    genie_answer: str | None = None  # Genie's summary/answer (shown before table)
    question: str | None = None  # User question (for chart type hint)

    def process_query_results(self) -> Activity:
        """
        Processes the result from a Genie query and formats it into an Activity object.

        This function takes a GenieResult object, extracts relevant information such as
        query description, metadata, and query results, and formats it into a message
        activity. If the query result contains tabular data, it generates an adaptive
        card with a table representation of the data.

        :returns: An Activity object containing the formatted response or an error message.
        :rtype: Activity

        :raises: Logs errors if required fields (e.g., result or data_array) are missing
                in the GenieResult object.
        """
        genie_answer = (self.genie_answer or "").strip()
        response = ""

        if self.statement_response:
            statement_response = self.statement_response
            logger.info(f"Found statement_response: {statement_response}")

            if statement_response.result and statement_response.result.data_array:
                manifest = statement_response.manifest
                columns = []

                if manifest and manifest.schema and manifest.schema.columns:
                    columns = manifest.schema.columns
                    logger.info(f"Schema columns: {columns}")
                else:
                    logger.warning("No manifest found in statement_response.")

                # Assign column widths: proportional to header length for full-width table fit
                col_output = []
                for col in columns:
                    display_len = len(_get_column_display_name(col.name))
                    w = max(2, min(5, (display_len // 4) + 2))
                    col_output.append({"width": w})

                data_array = statement_response.result.data_array
                logger.info(f"Data array: {data_array}")

                row_output = [
                    {
                        "type": "TableRow",
                        "cells": [
                            AdaptiveCardFactory.get_cell(
                                _get_column_display_name(col.name),
                                style=None,
                                wrap=False,
                                weight="Bolder",
                            )
                            for col in columns
                        ],
                    }
                ]

                for row in data_array:
                    cell_output = []
                    for value, col in zip(row, columns):
                        if value is None:
                            formatted_value = "NULL"
                        elif col.type_name in [
                            ColumnInfoTypeName.DECIMAL,
                            ColumnInfoTypeName.DOUBLE,
                            ColumnInfoTypeName.FLOAT,
                        ]:
                            fval = float(value)
                            col_lower = col.name.lower()
                            if "roi" in col_lower and ("pct" in col_lower or "percent" in col_lower):
                                if fval > 100:
                                    formatted_value = f"{fval:,.1f}% ({fval/100:.1f}x)"
                                else:
                                    formatted_value = f"{fval:,.2f}%"
                            else:
                                formatted_value = f"{fval:,.2f}"
                        elif col.type_name in [
                            ColumnInfoTypeName.INT,
                            ColumnInfoTypeName.LONG,
                            ColumnInfoTypeName.SHORT,
                        ]:
                            formatted_value = f"{int(value):,}"
                        else:
                            formatted_value = str(value)
                        cell_output.append(
                            AdaptiveCardFactory.get_cell(formatted_value)
                        )
                    row_output.append({"type": "TableRow", "cells": cell_output})

                chart_url = None
                chart_insights = None
                chart_data = build_chart_data(
                    columns,
                    data_array,
                    question_hint=self.question or "",
                )
                if chart_data:
                    chart_url = get_chart_url(chart_data)
                    # Use Genie's explanation for chart insights when available (same as Genie UI)
                    if genie_answer and not _is_user_echo(genie_answer, self.question or ""):
                        chart_insights = genie_answer.strip()
                        chart_insights = _clean_summary_text(chart_insights)
                        chart_insights = _fix_summary_count_mismatch(chart_insights, len(data_array))
                        # Single paragraph format, no separate headings - clearly explains the chart
                        chart_insights = _to_single_paragraph(chart_insights)
                    else:
                        chart_insights = generate_chart_insights(chart_data)

                # Summary: use Genie's answer exactly when available (match Genie UI)
                summary = ""
                if genie_answer and not _is_user_echo(genie_answer, self.question or ""):
                    summary = genie_answer.strip()
                    summary = _clean_summary_text(summary)
                    row_count = len(data_array)
                    summary = _fix_summary_count_mismatch(summary, row_count)
                    summary = _to_single_paragraph(summary)
                if not summary and self.query_description:
                    summary = self.query_description.strip()
                if not summary:
                    summary = _generate_summary_from_data(
                        columns, data_array, self.question or ""
                    ) or "Here are the results for your query."

                # Generate contextual follow-up questions
                followups = generate_followup_questions(
                    chart_data, chart_insights, summary, self.question or ""
                )

                activity = AdaptiveCardFactory.get_table_card(
                    genie_answer=summary,
                    response=response,
                    col_output=col_output,
                    row_output=row_output,
                    query=self.query or "No query provided",
                    chart_url=chart_url,
                    chart_insights=chart_insights,
                )
                activity.followup_questions = followups
                return activity
            else:
                logger.error(
                    f"Missing result or data_array in statement_response: {statement_response}"
                )
        elif self.message:
            response += f"{self.message}\n\n"
            return Activity(text=response, type=ActivityTypes.message)
        else:
            response += "No data available.\n\n"
            logger.error("No statement_response or message found in answer_json")

        return Activity(text=response, type=ActivityTypes.message)
