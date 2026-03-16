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

# Feedback action payload for like/dislike (used in Teams messageBack)
FEEDBACK_LIKE_DATA = {
    "msteams": {
        "type": "messageBack",
        "displayText": "Thanks for your feedback!",
        "text": "",
        "value": {"feedback": "like"},
    },
    "feedback": "like",
}
FEEDBACK_DISLIKE_DATA = {
    "msteams": {
        "type": "messageBack",
        "displayText": "Thanks for your feedback!",
        "text": "",
        "value": {"feedback": "dislike"},
    },
    "feedback": "dislike",
}


class AdaptiveCardFactory:
    @staticmethod
    def get_activity(attachments: list[Attachment] | None) -> Activity:
        return Activity(type=ActivityTypes.message, attachments=attachments)

    LOADING_STEPS = [
        ("Understanding your question…", "Analyzing your request"),
        ("Querying data…", "Fetching results from the database"),
        ("Building visualization…", "Preparing charts and insights"),
    ]

    @staticmethod
    def get_waiting_message(step: int = 1) -> Activity:
        """Step-based loader: 1=Understanding, 2=Querying, 3=Building."""
        steps = AdaptiveCardFactory.LOADING_STEPS
        idx = max(0, min(step - 1, len(steps) - 1))
        current_text, sub_text = steps[idx]

        body = []
        for i, (text, _) in enumerate(steps):
            is_active = i == idx
            body.append({
                "type": "Container",
                "style": "emphasis" if is_active else "default",
                "spacing": "Small",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"{'●' if is_active else '○'} {text}",
                        "wrap": True,
                        "size": "Medium" if is_active else "Small",
                        "weight": "Bolder" if is_active else "Default",
                    },
                ],
            })
        body.append({"type": "ProgressBar"})
        body.append({
            "type": "TextBlock",
            "text": sub_text,
            "spacing": "ExtraSmall",
            "size": "Small",
        })

        attachment = CardFactory.adaptive_card({
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": body,
        })
        return AdaptiveCardFactory.get_activity([attachment])

    @staticmethod
    def get_cell(text: str = "", style: str | None = None, wrap: bool = True) -> dict:
        """
        Returns a cell object for use in adaptive cards.
        style: optional ContainerStyle (emphasis, accent, etc.) for cell background.
        wrap: if False, keeps text on one line (use for headers).
        """
        cell: dict = {
            "type": "TableCell",
            "items": [
                {
                    "type": "TextBlock",
                    "text": text,
                    "wrap": wrap,
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
        export_csv_url: str | None = None,
        export_excel_url: str | None = None,
    ) -> Activity:
        """
        Returns an adaptive card: Genie answer → Table → Chart → Chart insights.
        """
        body: list[dict] = []

        # 1. Summary (always first, like Genie) - before table, no extra spacing
        if genie_answer:
            body.extend([
                {
                    "type": "Container",
                    "style": "emphasis",
                    "spacing": "None",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "Summary",
                            "wrap": True,
                            "size": "Large",
                            "weight": "Bolder",
                        },
                    ],
                },
                {
                    "type": "TextBlock",
                    "text": genie_answer,
                    "wrap": True,
                    "size": "Medium",
                    "spacing": "Small",
                },
            ])

        # 2. Table (double-layer container, expandable when many rows)
        max_preview_rows = 6  # header + 5 data rows
        rows_to_show = row_output[:max_preview_rows] if len(row_output) > max_preview_rows else row_output
        has_more_rows = len(row_output) > max_preview_rows

        body.extend([
            {
                "type": "Container",
                "style": "emphasis",
                "spacing": "Medium",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Results",
                        "wrap": True,
                        "size": "Large",
                        "weight": "Bolder",
                    },
                ],
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
                "type": "Container",
                "style": "emphasis",
                "spacing": "Medium",
                "separator": True,
                "items": [
                    {
                        "type": "Container",
                        "style": "accent",
                        "spacing": "Small",
                        "items": [
                            {
                                "type": "Table",
                                "roundedCorners": True,
                                "firstRowAsHeader": True,
                                "showGridLines": True,
                                "gridStyle": "emphasis",
                                "columns": col_output,
                                "rows": rows_to_show,
                            },
                        ],
                    },
                ],
            },
        ])
        if has_more_rows:
            data_rows = len(row_output) - 1
            preview_rows = min(5, data_rows)
            body.append({
                "type": "Container",
                "spacing": "Small",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"Showing {preview_rows} of {data_rows} rows. Tap **Expand table** below to view all.",
                        "wrap": True,
                        "size": "Small",
                    },
                ],
            })

        # 3. Chart + 4. Insights (below chart)
        if chart_url:
            body.append({
                "type": "Container",
                "style": "emphasis",
                "spacing": "Medium",
                "separator": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Visualization",
                        "wrap": True,
                        "size": "Large",
                        "weight": "Bolder",
                    },
                ],
            })
            body.append({
                "type": "Image",
                "url": chart_url,
                "size": "Stretch",
                "altText": "Chart",
            })
            if chart_insights:
                body.append({
                    "type": "Container",
                    "style": "emphasis",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "Insights",
                            "wrap": True,
                            "size": "Large",
                            "weight": "Bolder",
                        },
                    ],
                })
                body.append({
                    "type": "TextBlock",
                    "text": chart_insights,
                    "wrap": True,
                    "size": "Medium",
                })

        # Show SQL + View chart + Expand table as card actions
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
        if has_more_rows:
            data_rows = len(row_output) - 1
            preview_rows = min(5, data_rows)
            summary_line = f"Showing {preview_rows} of {data_rows} rows. Tap **Expand table** below to view all."
            expand_card_body = [
                {
                    "type": "Container",
                    "style": "emphasis",
                    "spacing": "Small",
                    "items": [
                        {"type": "TextBlock", "text": "Full table", "wrap": True, "size": "Large", "weight": "Bolder"},
                        {"type": "TextBlock", "text": summary_line, "wrap": True, "size": "Small", "spacing": "Small"},
                    ],
                },
                {
                    "type": "Table",
                    "roundedCorners": True,
                    "firstRowAsHeader": True,
                    "showGridLines": True,
                    "gridStyle": "emphasis",
                    "columns": col_output,
                    "rows": row_output,
                },
            ]
            actions.insert(0, {
                "type": "Action.ShowCard",
                "title": "Expand table",
                "card": {"type": "AdaptiveCard", "version": "1.5", "body": expand_card_body},
            })
        if export_csv_url:
            actions.append({
                "type": "Action.OpenUrl",
                "title": "Export to CSV",
                "url": export_csv_url,
            })
        if export_excel_url:
            actions.append({
                "type": "Action.OpenUrl",
                "title": "Export for Excel",
                "url": export_excel_url,
            })
        if chart_url:
            actions.append({
                "type": "Action.OpenUrl",
                "title": "View chart in browser",
                "url": chart_url,
            })

        # Like/dislike feedback buttons on every response
        actions.extend([
            {
                "type": "Action.Submit",
                "title": "👍 Helpful",
                "data": FEEDBACK_LIKE_DATA,
            },
            {
                "type": "Action.Submit",
                "title": "👎 Not helpful",
                "data": FEEDBACK_DISLIKE_DATA,
            },
        ])

        card_payload: dict = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": body,
            "actions": actions,
        }

        attachment = CardFactory.adaptive_card(card_payload)

        return AdaptiveCardFactory.get_activity([attachment])

    @staticmethod
    def get_feedback_card_attachment() -> list[Attachment]:
        """Returns a minimal Adaptive Card with like/dislike feedback buttons."""
        card = {
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [],
            "actions": [
                {"type": "Action.Submit", "title": "👍 Helpful", "data": FEEDBACK_LIKE_DATA},
                {"type": "Action.Submit", "title": "👎 Not helpful", "data": FEEDBACK_DISLIKE_DATA},
            ],
        }
        return CardFactory.adaptive_card(card)

    @staticmethod
    def get_text_with_feedback_activity(text: str) -> Activity:
        """Returns an Activity with text and like/dislike feedback buttons."""
        return Activity(
            type=ActivityTypes.message,
            text=text,
            attachments=AdaptiveCardFactory.get_feedback_card_attachment(),
        )

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
            "body": [
                {"type": "TextBlock", "text": body_text, "wrap": True, "size": "Medium"},
            ],
            "actions": actions + [
                {"type": "Action.Submit", "title": "👍 Helpful", "data": FEEDBACK_LIKE_DATA},
                {"type": "Action.Submit", "title": "👎 Not helpful", "data": FEEDBACK_DISLIKE_DATA},
            ],
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
            "body": [
                {"type": "TextBlock", "text": text, "wrap": True, "size": "Medium"},
            ],
            "actions": actions,
        }
        attachment = CardFactory.adaptive_card(card)
        return AdaptiveCardFactory.get_activity([attachment])
