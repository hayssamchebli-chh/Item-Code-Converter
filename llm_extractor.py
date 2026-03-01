from openai import OpenAI
import json
import os
import re

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
You are a BOQ (Bill of Quantities) structure extraction engine.

Your job is ONLY to extract structured cable items from messy electrical BOQ text and return them as JSON.

You MUST NOT:
- Apply engineering conversion rules
- Convert cable codes
- Calculate rolls or meters
- Split cable logic
- Change cable types
- Infer missing technical values
- Guess sizes that are not explicitly written

============================================================
INPUT CAN BE IN MANY FORMS
============================================================

A) ROW FORMAT (already complete):
Example:
"3 x 4mm2 m 80"
Extract as ONE item.

B) BLOCK FORMAT (VERY IMPORTANT):
Example:

Single Wire NYA 4mm2

1
RED
Roll
5

2
Yellow
Roll
5

Rules for BLOCK FORMAT:
- The first descriptive line is the HEADER (cable identity and size).
- The following sub-rows contain only attributes like color/unit/qty.
- You MUST merge header + sub-row into a full item.
- NEVER output partial items like: "Yellow Roll 5"
- Unit can appear on its own line (e.g., "ROLL") and applies to the closest preceding item/sub-row.
- Quantity is the FIRST numeric value that appears AFTER the unit for that same item.
- DO NOT steal a number from the next item.

CRITICAL:
- If an item does not have an explicit numeric quantity, SKIP it.
  (Do not create an item with quantity=null.)

============================================================
FIRE SECTION DETECTION
============================================================
If a section header contains any of:
- fire
- fire resistant
- FR
- CEI
then set is_fire_section=true for ALL following items until another cable section header appears.

If a row itself contains fire keywords, that item must have is_fire_section=true.

============================================================
OUTPUT FORMAT (STRICT)
============================================================
Return STRICT JSON array ONLY. No text. No markdown. No ```.

Each item MUST contain exactly these fields:
{
  "description": "...",
  "raw_text": "...",
  "size_text": null or "...",
  "color": null or "...",
  "unit": null or "...",
  "quantity": number,
  "is_fire_section": boolean
}

Rules:
- description should be a clean merged description including size and color if present.
- raw_text should be the merged original meaning (header + subrow).
- If color not mentioned, use null.
- If unit not mentioned, use null.
- If size not explicitly written, use null.
- Ignore headings like: Item, Description, Unit, Quantity, Total, Notes.
- Only output real cable entries with a numeric quantity.
"""

#########################################
#########################################

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?", "", s.strip(), flags=re.IGNORECASE).strip()
        s = re.sub(r"```$", "", s.strip()).strip()
    return s

def _extract_json_array(s: str) -> str:
    s = s.strip()
    start = s.find("[")
    end = s.rfind("]")
    if start != -1 and end != -1 and end > start:
        return s[start:end+1]
    return s

def _remove_control_chars_outside_strings(s: str) -> str:
    """
    Removes ASCII control chars globally. This is a blunt tool.
    Keep it, but we’ll also add a smarter sanitizer below.
    """
    return re.sub(r"[\x00-\x1F\x7F]", "", s)


def _sanitize_json_control_chars(s: str) -> str:
    """
    Fix common LLM JSON issues:
    - raw newlines/tabs inside quoted strings
    - other control chars inside strings

    We do NOT try to "engineer" anything. We only make JSON parseable.
    """
    out = []
    in_str = False
    esc = False

    for ch in s:
        if in_str:
            if esc:
                # keep escaped char as-is
                out.append(ch)
                esc = False
                continue

            if ch == "\\":
                out.append(ch)
                esc = True
                continue

            # JSON strings cannot contain raw newlines or tabs.
            if ch == "\n" or ch == "\r":
                out.append("\\n")
                continue
            if ch == "\t":
                out.append("\\t")
                continue

            # Other ASCII control chars inside strings → replace with space
            if ord(ch) < 32:
                out.append(" ")
                continue

            if ch == '"':
                in_str = False
                out.append(ch)
                continue

            out.append(ch)
        else:
            if ch == '"':
                in_str = True
                out.append(ch)
                continue

            # Outside strings, remove control chars outright
            if ord(ch) < 32:
                continue

            out.append(ch)

    return "".join(out)


def _extract_top_level_json_objects(s: str):
    """
    Salvage parser: scan text and extract substrings that look like top-level JSON objects { ... }
    respecting strings and escapes, so we don't split in the middle of a quoted string.
    """
    objs = []
    in_str = False
    esc = False
    depth = 0
    start = None

    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue

        # not in string
        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    objs.append(s[start:i+1])
                    start = None

    return objs


def extract_structure_from_text(raw_text: str):
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract structured cable items from:\n\n{raw_text}"}
        ],
    )

    content = resp.choices[0].message.content or ""
    content = _strip_code_fences(content)
    content = _extract_json_array(content)

    # First sanitize (smart), then also remove any remaining control chars outside strings
    content = _sanitize_json_control_chars(content)
    content = _remove_control_chars_outside_strings(content)

    items = None

    # 1) Fast path: normal JSON parse
    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        items = None

    # 2) Salvage path: parse objects one-by-one, skip invalid ones
    if items is None:
        salvage = []
        for obj_txt in _extract_top_level_json_objects(content):
            obj_txt = _sanitize_json_control_chars(obj_txt)
            try:
                salvage.append(json.loads(obj_txt))
            except Exception:
                # skip bad object
                continue
        items = salvage

    # Handle {"items":[...]} shape
    if isinstance(items, dict):
        if "items" in items and isinstance(items["items"], list):
            items = items["items"]
        else:
            items = []

    if not isinstance(items, list):
        items = []

    # Safety cleanup (drop bad items; keep the rest)
    cleaned = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            qty = it.get("quantity", None)
            if qty is None:
                continue
            qty = float(qty)
            if qty <= 0:
                continue

            cleaned.append({
                "description": it.get("description"),
                "raw_text": it.get("raw_text"),
                "size_text": it.get("size_text"),
                "color": it.get("color"),
                "unit": it.get("unit"),
                "quantity": qty,
                "is_fire_section": bool(it.get("is_fire_section", False))
            })
        except Exception:
            continue

    return cleaned
