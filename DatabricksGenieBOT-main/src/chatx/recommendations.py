"""Contextual recommendation and error recovery helpers."""

from chatx.const import RECOMMENDATION_QUESTIONS

# Concrete examples for error recovery
ERROR_SUGGESTIONS = [
    "Show ROI by channel",
    "What's the spend by region?",
    "Which channels perform best?",
    "Compare pipeline across regions",
]


def get_error_recovery_suggestions(error_type: str = "generic") -> list[str]:
    """Return 2-3 concrete question suggestions for error recovery."""
    return ERROR_SUGGESTIONS[:3]


def generate_contextual_recommendations(
    last_question: str,
    genie_answer: str = "",
    followup_questions: list[str] | None = None,
) -> list[str]:
    """
    Generate 3-4 recommendation questions based on the last question and context.
    Uses followup_questions if provided, else derives from question/answer.
    """
    if followup_questions and len(followup_questions) >= 2:
        # Use AI-generated follow-ups, pad with defaults if needed
        result = list(followup_questions)[:3]
        for q in RECOMMENDATION_QUESTIONS:
            if q not in result and len(result) < 4:
                result.append(q)
        return result[:4]

    q_lower = (last_question or "").lower()
    recs: list[str] = []

    # Map question patterns to contextual follow-ups
    if "roi" in q_lower:
        recs.extend(["Drill into top channel", "Compare ROI by region", "Show spend vs pipeline"])
    elif "spend" in q_lower:
        recs.extend(["Show ROI by channel", "Compare spend by region", "Which channels have highest spend?"])
    elif "channel" in q_lower:
        recs.extend(["Compare pipeline across regions", "Show spend by channel", "Drill into top channel"])
    elif "region" in q_lower:
        recs.extend(["Compare channels by region", "Show ROI by region", "Breakdown by channel"])
    elif "pipeline" in q_lower:
        recs.extend(["Compare pipeline by channel", "Show ROI by channel", "Which regions lead pipeline?"])

    # Add defaults to fill
    for q in RECOMMENDATION_QUESTIONS:
        if q not in recs and len(recs) < 4:
            recs.append(q)

    return recs[:4]
