"""Step 1: Tạo script từ topic bằng OpenAI GPT."""
import os
from openai import OpenAI
from dotenv import load_dotenv

from .cache import get, set

load_dotenv()

PROMPT_TEMPLATE = """Viết script video ngắn (30-60 giây) cho TikTok/YouTube Shorts về chủ đề: "{topic}"

Yêu cầu:
- Hook mạnh trong 3 giây đầu
- Nội dung súc tích, dễ nhớ
- Kết thúc bằng CTA rõ ràng
- Chỉ output script thuần text, không đánh số, không markdown"""


def generate_script(topic: str, use_cache: bool = True) -> str:
    cache_key = f"script:{topic}"
    if use_cache:
        cached = get(cache_key, "script")
        if cached:
            return cached

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Bạn là copywriter chuyên viết script video viral."},
            {"role": "user", "content": PROMPT_TEMPLATE.format(topic=topic)},
        ],
        max_tokens=500,
    )
    script = response.choices[0].message.content.strip()

    if use_cache:
        set(cache_key, script, "script")

    return script
