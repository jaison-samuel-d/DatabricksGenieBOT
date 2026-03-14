import logging

import sqlparse
from botbuilder.core import CardFactory
from botbuilder.schema import (
    Attachment,
    ActivityTypes,
    Activity,
    CardAction,
    ActionTypes,
    SuggestedActions,
)

from chatx.const import WAITING_MESSAGE, RECOMMENDATION_QUESTIONS, RECOMMENDATION_PROMPT

# Log
logger = logging.getLogger(__name__)


class AdaptiveCardFactory:
    @staticmethod
    def get_activity(attachments: list[Attachment] | None) -> Activity:
        return Activity(type=ActivityTypes.message, attachments=attachments)

    @staticmethod
    def get_waiting_message() -> Activity:
        attachment = CardFactory.adaptive_card(
            {
                "type": "AdaptiveCard",
                "version": "1.5",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "One moment...",
                        "wrap": True,
                        "size": "Large",
                        "weight": "Bolder",
                    },
                    {"type": "ProgressBar"},
                    {
                        "type": "TextBlock",
                        "text": WAITING_MESSAGE,
                        "spacing": "ExtraSmall",
                        "size": "Small",
                    },
                ],
            }
        )
        return AdaptiveCardFactory.get_activity([attachment])

    @staticmethod
    def get_cell(text: str = "", style: str | None = None) -> dict:
        """
        Returns a cell object for use in adaptive cards.
        style: optional ContainerStyle (emphasis, accent, etc.) for cell background.
        """
        cell: dict = {
            "type": "TableCell",
            "items": [
                {
                    "type": "TextBlock",
                    "text": text,
                    "wrap": True,
                }
            ],
        }
        if style:
            cell["style"] = style
        return cell

    @staticmethod
    def get_table_card(
        genie_answer: str,
        response: str,
        col_output: list[dict[str, int]],
        row_output: list[dict[str, any]],
        query: str,
        chart_url: str | None = None,
        chart_insights: str | None = None,
    ) -> Activity:
        """
        Returns an adaptive card: Genie answer → Table → Chart → Chart insights.
        """
        body: list[dict] = []

        # Divider above Summary (Teams rejects pixel height; use separator instead)
        body.append({
            "type": "Container",
            "items": [{"type": "TextBlock", "text": "\u200B", "wrap": True}],
            "style": "emphasis",
            "separator": True,
        })

        # 1. Summary (always first, like Genie) - before table
        if genie_answer:
            body.extend([
                {
                    "type": "TextBlock",
                    "text": "Summary",
                    "wrap": True,
                    "size": "Large",
                    "weight": "Bolder",
                },
                {
                    "type": "TextBlock",
                    "text": genie_answer,
                    "wrap": True,
                    "size": "Medium",
                },
                {"type": "TextBlock", "text": "", "separator": True},
            ])

        # 2. Table
        body.extend([
            {
                "type": "TextBlock",
                "text": "Results",
                "wrap": True,
                "size": "Large",
                "weight": "Bolder",
            },
            {
                "type": "Container",
                "layouts": [
                    {"type": "Layout.Flow", "horizontalItemsAlignment": "left"}
                ],
                "items": [
                    {"type": "Icon", "name": "TableLightning", "size": "Small"},
                    {"type": "TextBlock", "text": response, "wrap": True},
                ],
            },
            {
                "type": "Table",
                "roundedCorners": True,
                "firstRowAsHeader": True,
                "showGridLines": True,
                "gridStyle": "accent",
                "columns": col_output,
                "rows": row_output,
            },
        ])

        # 3. Chart + 4. Insights (below chart)
        if chart_url:
            body.append({"type": "TextBlock", "text": "", "separator": True})
            body.append({
                "type": "TextBlock",
                "text": "Visualization",
                "wrap": True,
                "size": "Large",
                "weight": "Bolder",
            })
            body.append({
                "type": "Image",
                "url": chart_url,
                "size": "Stretch",
                "altText": "Chart",
            })
            if chart_insights:
                body.append({
                    "type": "TextBlock",
                    "text": "Insights",
                    "wrap": True,
                    "size": "Large",
                    "weight": "Bolder",
                    "spacing": "Medium",
                })
                body.append({
                    "type": "TextBlock",
                    "text": chart_insights,
                    "wrap": True,
                    "size": "Medium",
                })

        # Show SQL + View chart as card actions (renders in card footer, separate from recommendations)
        formatted_sql = sqlparse.format(query, reindent=True, keyword_case="upper")
        actions: list[dict] = [
            {
                "type": "Action.ShowCard",
                "title": "Show SQL query",
                "card": {
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": formatted_sql,
                            "wrap": True,
                            "size": "Small",
                        }
                    ],
                },
            },
        ]
        if chart_url:
            actions.append({
                "type": "Action.OpenUrl",
                "title": "View chart in browser",
                "url": chart_url,
            })

        card_payload: dict = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": body,
            "actions": actions,
        }

        attachment = CardFactory.adaptive_card(card_payload)

        return AdaptiveCardFactory.get_activity([attachment])

    @staticmethod
    def get_kpi_card(metrics: list[dict[str, str]] | None = None) -> Activity | None:
        """Build a static KPI card from configured metrics. No query is run."""
        from chatx.const import WELCOME_KPI_METRICS

        facts = metrics or WELCOME_KPI_METRICS
        if not facts:
            return None

        # Build KPI blocks in a 2-column grid for a clean, smooth layout
        kpi_items = []
        for m in facts:
            title = m.get("title", "")
            value = m.get("value", "—")
            kpi_items.append({
                "type": "Container",
                "style": "emphasis",
                "spacing": "Small",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": title,
                        "wrap": True,
                        "size": "Small",
                        "isSubtle": True,
                    },
                    {
                        "type": "TextBlock",
                        "text": value,
                        "wrap": True,
                        "size": "Medium",
                        "weight": "Bolder",
                        "spacing": "None",
                    },
                ],
            })

        # Pair KPIs into rows (2 per row) for a clean grid
        rows = []
        for i in range(0, len(kpi_items), 2):
            pair = kpi_items[i : i + 2]
            cols = [{"type": "Column", "width": "stretch", "items": [p]} for p in pair]
            rows.append({"type": "ColumnSet", "columns": cols, "spacing": "Medium"})

        card = {
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [
                {
                    "type": "Container",
                    "style": "emphasis",
                    "spacing": "Medium",
                    "separator": True,
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "Key metrics",
                            "wrap": True,
                            "size": "Large",
                            "weight": "Bolder",
                        },
                        {"type": "Container", "items": rows, "spacing": "Medium"},
                    ],
                },
            ],
        }
        return AdaptiveCardFactory.get_activity([CardFactory.adaptive_card(card)])

    @staticmethod
    def get_recommendation_activity(prompt: str | None = None) -> Activity:
        """Returns an activity with 4 clickable recommendation questions as SuggestedActions."""
        actions = [
            CardAction(title=q, type=ActionTypes.im_back, value=q)
            for q in RECOMMENDATION_QUESTIONS
        ]
        activity = Activity(type=ActivityTypes.message, text=prompt or RECOMMENDATION_PROMPT)
        activity.suggested_actions = SuggestedActions(actions=actions)
        return activity

    @staticmethod
    def get_recommendation_card_activity(prompt: str | None = None) -> Activity:
        """Returns recommendations as a separate Adaptive Card (only 4 questions, no Show SQL/View chart)."""
        text = prompt or RECOMMENDATION_PROMPT
        actions = [
            {
                "type": "Action.Submit",
                "title": q,
                "data": {
                    "msteams": {
                        "type": "messageBack",
                        "displayText": q,
                        "text": q,
                        "value": {"question": q},
                    },
                    "question": q,
                },
            }
            for q in RECOMMENDATION_QUESTIONS
        ]
        card = {
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [
                {"type": "TextBlock", "text": text, "wrap": True, "size": "Medium"},
            ],
            "actions": actions,
        }
        attachment = CardFactory.adaptive_card(card)
        return AdaptiveCardFactory.get_activity([attachment])
