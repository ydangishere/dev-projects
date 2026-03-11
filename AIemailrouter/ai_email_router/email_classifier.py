"""Email classification using OpenAI API."""

from typing import List, Dict
from openai import OpenAI
from config import CLASSIFICATION_PROMPT, CATEGORIES, OPENAI_MODEL


def classify_email(client: OpenAI, email_text: str) -> str:
    """
    Send a single email to OpenAI and get the category.
    Returns the category name (sales, support, billing, spam, other).
    """
    if not email_text.strip():
        return "other"

    prompt = CLASSIFICATION_PROMPT.format(email_text=email_text.strip())
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    result = response.choices[0].message.content.strip().lower()

    # Normalize: ensure result is one of the valid categories
    for cat in CATEGORIES:
        if cat in result:
            return cat
    return "other"


def classify_emails(client: OpenAI, emails: List[str]) -> List[Dict]:
    """
    Classify multiple emails. Returns list of {"email": str, "category": str}.
    """
    results = []
    for email_text in emails:
        email_text = email_text.strip()
        if not email_text:
            continue
        category = classify_email(client, email_text)
        results.append({"email": email_text, "category": category})
    return results
