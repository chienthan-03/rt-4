from openai import OpenAI
from backend.config import settings
from backend.llm_json import parse_llm_json

# Initialize client lazily to avoid crash if API key is not yet set
_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
    return _client

def build_tag_prompt(name: str, duration_ms: int) -> str:
    return f"""Bạn là chuyên gia về meme sound effects. 

Sound name: "{name}"
Duration: {duration_ms}ms

Phân tích và trả về JSON với các trường sau:
{{
  "emotion": "shock|sadness|hype|fail|awkward|dramatic|funny|cringe|win",
  "tier": "emphasis|comedy",
  "intensity": 0.0-1.0,
  "timing_type": "instant|buildup|reaction",
  "tags": ["tag1", "tag2"],
  "event_types": ["event1", "event2"],
  "description": "mô tả ngắn để embedding search"
}}

Chỉ trả về JSON, không giải thích."""

def tag_sound(name: str, duration_ms: int) -> dict:
    client = get_client()
    prompt = build_tag_prompt(name, duration_ms)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=512,
    )
    raw = response.choices[0].message.content or ""
    return parse_llm_json(raw)
