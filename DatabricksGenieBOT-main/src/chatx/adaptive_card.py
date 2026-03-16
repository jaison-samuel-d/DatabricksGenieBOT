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

from chatx.const import RECOMMENDATION_QUESTIONS, RECOMMENDATION_PROMPT

# Log
logger = logging.getLogger(__name__)

class AdaptiveCardFactory:
    @staticmethod
    def get_activity(attachments: list[Attachment] | None) -> Activity:
        return Activity(type=ActivityTypes.message, attachments=attachments)

    @staticmethod
    def get_waiting_message(step: int = 1) -> Activity:
        """Loading indicator. Replaced by response when ready via update_activity."""
        attachment = CardFactory.adaptive_card({
            "type": "AdaptiveCard",
            "version": "1.5",
            "msteams": {"width": "full"},
            "body": [
                {
                    "type": "TextBlock",
                    "text": "One moment please…",
                    "wrap": True,
                    "size": "Large",
                    "weight": "Bolder",
                },
                {"type": "ProgressBar"},
                {
                    "type": "TextBlock",
                    "text": "Looking that up for you…",
                    "spacing": "ExtraSmall",
                    "size": "Small",
                },
            ],
        })
        return AdaptiveCardFactory.get_activity([attachment])

    @staticmethod
    def get_cell(text: str = "", style: str | None = None, wrap: bool = True, weight: str = "Default") -> dict:
        """
        Returns a cell object for use in adaptive cards.
        style: optional ContainerStyle (emphasis, accent, etc.) for cell background.
        wrap: if False, keeps text on one line (use for headers).
        weight: TextBlock weight (Default, Bolder) for headers.
        """
        cell: dict = {
            "type": "TableCell",
            "items": [
                {
                    "type": "TextBlock",
                    "text": text,
                    "wrap": wrap,
                    "weight": weight,
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

        # 1. Summary content only (no heading)
        if genie_answer:
            body.append({
                "type": "TextBlock",
                "text": genie_answer,
                "wrap": True,
                "size": "Medium",
                "spacing": "Small",
            })

        # 2. Result table (content only, no heading or row count)
        body.extend([
            {
                "type": "Container",
                "spacing": "Small",
                "separator": True,
                "items": [
                    {
                        "type": "Container",
                        "spacing": "None",
                        "separator": True,
                        "items": [
                            {
                                "type": "Container",
                                "spacing": "None",
                                "separator": True,
                                "items": [
                                    {
                                        "type": "Table",
                                        "firstRowAsHeader": True,
                                        "showGridLines": True,
                                        "gridStyle": "default",
                                        "columns": col_output,
                                        "rows": row_output,
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        ])

        # 3. Chart + insights (content only, no heading) - full-width layout
        if chart_url:
            body.append({
                "type": "Container",
                "horizontalAlignment": "Stretch",
                "spacing": "None",
                "items": [
                    {
                        "type": "Image",
                        "url": chart_url,
                        "size": "Stretch",
                        "altText": "Chart",
                    },
                ],
            })
            if chart_insights:
                body.append({
                    "type": "TextBlock",
                    "text": chart_insights,
                    "wrap": True,
                    "size": "Medium",
                    "spacing": "Medium",
                })

        # Show SQL + View chart as card actions
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
            "msteams": {"width": "full"},
            "body": body,
            "actions": actions,
        }

        attachment = CardFactory.adaptive_card(card_payload)

        return AdaptiveCardFactory.get_activity([attachment])

    @staticmethod
    def get_error_recovery_activity(
        message: str,
        suggestions: list[str],
    ) -> Activity:
        """Returns an error message with concrete suggestions as clickable actions."""
        suggestion_text = "Try asking: " + " | ".join(f"\"{s}\"" for s in suggestions[:3])
        body_text = f"{message}\n\n{suggestion_text}"
        actions = [
            {
                "type": "Action.Submit",
                "title": s,
                "data": {
                    "msteams": {"type": "messageBack", "displayText": s, "text": s, "value": {"question": s}},
                    "question": s,
                },
            }
            for s in suggestions[:3]
        ]
        card = {
            "type": "AdaptiveCard",
            "version": "1.2",
            "msteams": {"width": "full"},
            "body": [
                {"type": "TextBlock", "text": body_text, "wrap": True, "size": "Medium"},
            ],
            "actions": actions,
        }
        return Activity(
            type=ActivityTypes.message,
            text=body_text,
            attachments=CardFactory.adaptive_card(card),
        )

    @staticmethod
    def get_recommendation_activity(
        prompt: str | None = None,
        questions: list[str] | None = None,
    ) -> Activity:
        """Returns an activity with clickable recommendation questions as SuggestedActions."""
        qs = questions if questions else RECOMMENDATION_QUESTIONS
        actions = [
            CardAction(title=q, type=ActionTypes.im_back, value=q)
            for q in qs[:6]
        ]
        activity = Activity(type=ActivityTypes.message, text=prompt or RECOMMENDATION_PROMPT)
        activity.suggested_actions = SuggestedActions(actions=actions)
        return activity

    @staticmethod
    def get_recommendation_card_activity(
        prompt: str | None = None,
        questions: list[str] | None = None,
    ) -> Activity:
        """Returns recommendations as a separate Adaptive Card."""
        text = prompt or RECOMMENDATION_PROMPT
        qs = questions if questions else RECOMMENDATION_QUESTIONS
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
            for q in qs[:6]
        ]
        card = {
            "type": "AdaptiveCard",
            "version": "1.2",
            "msteams": {"width": "full"},
            "body": [
                {"type": "TextBlock", "text": text, "wrap": True, "size": "Medium"},
            ],
            "actions": actions,
        }
        attachment = CardFactory.adaptive_card(card)
        return AdaptiveCardFactory.get_activity([attachment])
