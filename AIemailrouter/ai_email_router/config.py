"""Configuration for AI Email Router."""

import os

# OpenAI API - lấy từ biến môi trường OPENAI_API_KEY
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Telegram - chỉ cần set 1 lần (tạo bot qua @BotFather). User chỉ nhập username.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Categories for email classification
CATEGORIES = ["sales", "support", "billing", "spam", "other"]

# Output file path
OUTPUT_FILE = "email_classification_results.json"

# OpenAI model
OPENAI_MODEL = "gpt-3.5-turbo"

# Classification prompt template
CLASSIFICATION_PROMPT = """Classify the following customer email into one category:

sales
support
billing
spam
other

Only return the category name.

Email:
{email_text}"""
