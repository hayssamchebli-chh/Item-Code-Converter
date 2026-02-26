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

You are NOT allowed to:
- Apply engineering conversion rules
- Convert cable codes
- Calculate rolls or meters
- Split cable logic
- Change cable types
- Infer missing technical values
- Guess sizes that are not explicitly written

Your job is ONLY to restructure messy text into clean structured cable items.

------------------------------------------------------------
🔎 INPUT MAY BE IN 2 DIFFERENT FORMS
------------------------------------------------------------

1️⃣ ROW FORMAT
Each line already contains:
- description
- unit
- quantity

Example:
3 x 4mm2 m 80

In this case, extract it directly as one structured item.

------------------------------------------------------------

2️⃣ BLOCK FORMAT (VERY IMPORTANT)

Sometimes items are written in blocks like this:

Single Wire NYA 4mm2

1
RED
Roll
5

2
Yellow
Roll
5

3
Black
Roll
15

In this case:

• The first line is the HEADER describing the cable.
• The following rows contain color + unit + quantity.
• These sub-rows DO NOT contain size or cable identity.
• You MUST merge the header with each sub-row.

Example input block:

Single Wire NYA 4mm2
RED Roll 5
Yellow Roll 5

Correct structured output:

[
  {
    "description": "Single Wire NYA 4mm2 RED",
    "raw_text": "Single Wire NYA 4mm2 RED Roll 5",
    "size_text": "4mm2",
    "color": "RED",
    "unit": "Roll",
    "quantity": 5,
    "is_fire_section": false
  },
  {
    "description": "Single Wire NYA 4mm2 Yellow",
    "raw_text": "Single Wire NYA 4mm2 Yellow Roll 5",
    "size_text": "4mm2",
    "color": "Yellow",
    "unit": "Roll",
    "quantity": 5,
    "is_fire_section": false
  }
]

❗ NEVER output partial rows like:
"Yellow Roll 5"
without merging it with its cable header.

------------------------------------------------------------
🔥 FIRE SECTION DETECTION
------------------------------------------------------------

If a section header contains:
- fire
- fire resistant
- FR
- CEI

Then set:
"is_fire_section": true

All items following that header belong to fire section until another cable section appears.

If a row itself contains fire keywords, mark that item as:
"is_fire_section": true

------------------------------------------------------------
📦 OUTPUT FORMAT RULES
------------------------------------------------------------

Return STRICT JSON array only.
Do NOT return explanation.
Do NOT wrap inside markdown.
Do NOT use ```json blocks.
Return only valid JSON.

Each item MUST contain:

{
  "description": "...",
  "raw_text": "...",
  "size_text": "...",
  "color": null or "...",
  "unit": null or "...",
  "quantity": number,
  "is_fire_section": boolean
}

If color is not mentioned → use null.
If unit is not mentioned → use null.
If size is not explicitly written → use null.
If quantity is missing → do NOT create the item.

Do NOT create fake items.
Only extract real cable items.
Ignore headings like:
Item
Description
Unit
Quantity
Notes
Total

Only return real cable entries."""

def extract_structure_from_text(raw_text: str):
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # or "llama-3.1-8b-instant" for cheaper/faster -- llama-3.1-70b-versatile
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




