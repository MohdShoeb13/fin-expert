"""Regulatory disclaimer handling.

The assistant provides education, not financial advice. Every user-facing
response must carry the disclaimer (graded compliance requirement).
"""

EDUCATIONAL_DISCLAIMER = (
    "📘 *This is educational content, not financial advice. "
    "Consult a licensed financial advisor before making investment decisions.*"
)


def with_disclaimer(text: str) -> str:
    if EDUCATIONAL_DISCLAIMER in text:
        return text
    return f"{text}\n\n{EDUCATIONAL_DISCLAIMER}"
