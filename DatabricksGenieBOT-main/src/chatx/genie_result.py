from dataclasses import dataclass
import logging

from databricks.sdk.service.sql import StatementResponse, ColumnInfoTypeName
from databricks.sdk.service.dashboards import GenieResultMetadata
from botbuilder.schema import Activity, ActivityTypes

from chatx.adaptive_card import AdaptiveCardFactory
from chatx.chart_builder import build_chart_data, get_chart_url, generate_chart_insights

# Log
logger = logging.getLogger(__name__)

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

        if self.query_result_metadata:
            metadata = self.query_result_metadata
            if metadata.row_count:
                response += f"**Row Count:** {metadata.row_count}\n\n"

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

                col_output = [{"width": 3} for _ in columns]

                data_array = statement_response.result.data_array
                logger.info(f"Data array: {data_array}")

                row_output = [
                    {
                        "type": "TableRow",
                        "cells": [
                            AdaptiveCardFactory.get_cell(col.name) for col in columns
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
                            formatted_value = f"{float(value):,.2f}"
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
                    chart_insights = generate_chart_insights(chart_data)
                    if self.query_description:
                        chart_insights = f"{self.query_description}\n\n{chart_insights}"

                # Summary: use Genie's answer only if it's a real summary, not user echo
                summary = ""
                if genie_answer and not _is_user_echo(genie_answer, self.question or ""):
                    summary = genie_answer.strip()
                if not summary and self.query_description:
                    summary = self.query_description.strip()
                if not summary or summary.lower() in ("here are the results for your query.", "no attachment found"):
                    data_summary = _generate_summary_from_data(
                        columns, data_array, self.question or ""
                    )
                    summary = data_summary or "Here are the results for your query."

                return AdaptiveCardFactory.get_table_card(
                    genie_answer=summary,
                    response=response,
                    col_output=col_output,
                    row_output=row_output,
                    query=self.query or "No query provided",
                    chart_url=chart_url,
                    chart_insights=chart_insights,
                )
            else:
                logger.error(
                    f"Missing result or data_array in statement_response: {statement_response}"
                )
        elif self.message:
            response += f"{self.message}\n\n"
            return Activity(
                text=response,
                type=ActivityTypes.message,
            )
        else:
            response += "No data available.\n\n"
            logger.error("No statement_response or message found in answer_json")

        return Activity(text=response, type=ActivityTypes.message)
