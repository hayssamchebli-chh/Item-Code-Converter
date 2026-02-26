from openai import OpenAI
import json
import os

# Create client using environment variable
client = OpenAI(api_key=os.getenv("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"))

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

    response = client.chat.completions.create(
        model="gpt-4o-mini",   # good balance cost/performance
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract structured cable items from:\n\n{raw_text}"}
        ],
    )

    content = response.choices[0].message.content.strip()

    # Sometimes model wraps JSON in ```json blocks — remove them safely
    if content.startswith("```"):
        content = content.strip("`")
        content = content.replace("json", "", 1).strip()

    return json.loads(content)
