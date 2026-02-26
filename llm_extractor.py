from openai import OpenAI
import json
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq is OpenAI-compatible via this base_url
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
You are a BOQ (Bill of Quantities) structure extraction engine.

Your task is ONLY to extract structured cable items from messy electrical BOQ text.

You must NOT:
- Apply engineering conversion rules.
- Change cable types.
- Calculate quantities.
- Split cable logic.
- Infer missing values.

Return strict JSON array only.

Each item must contain:
{
  "description": "...",
  "raw_text": "...",
  "size_text": "...",
  "color": null or "...",
  "unit": null or "...",
  "quantity": number,
  "is_fire_section": boolean
}
"""

def extract_structure_from_text(raw_text: str):
    resp = client.chat.completions.create(
        model="llama-3.1-70b-versatile",  # or "llama-3.1-8b-instant" for cheaper/faster
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract structured cable items from:\n\n{raw_text}"}
        ],
    )

    content = resp.choices[0].message.content.strip()

    # Remove ```json ... ``` if present
    if content.startswith("```"):
        content = content.strip("`").strip()
        content = content.replace("json", "", 1).strip()

    return json.loads(content)


