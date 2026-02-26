import re
import pandas as pd

ROLL_LENGTH = 92

###########################################################################################################################
COLOR_MAP = {
    "red": "RD", "rd": "RD",
    "yellow": "YL", "yl": "YL",
    "black": "BK", "bk": "BK",
    "blue": "BL", "bl": "BL", "bu": "BL",
    "brown": "BR", "br": "BR",
    "grey": "GY", "gray": "GY", "gy": "GY",
    "white": "WT", "wt": "WT",
    "orange": "OR", "or": "OR",
}

###########################################################################################################################
def format_size(size):
    return str(int(size)) if float(size).is_integer() else str(size)

def is_fire_header(text: str) -> bool:
    """
    Detect if a section header represents fire resistant cables.
    """
    if not text:
        return False

    text = text.lower()
    return "fire" in text or "fire resistant" in text


def is_new_cable_section(text: str) -> bool:
    """
    Detect if this line represents a new cable type section.
    """
    if not text:
        return False

    text = text.lower()

    return (
        "cu/pvc" in text
        or "cu/fire" in text
        or "fire resistant" in text
        or "swa" in text
        or "xlpe" in text
    )


def row_contains_fire(text: str) -> bool:
    """
    Detect fire keyword inside item row itself.
    """
    if not text:
        return False

    return "fire" in text.lower()

# =========================================================
# PARSER
# =========================================================
def parse_line(text: str):
    text = text.strip()
    # -----------------------------------------------------
    # Extract quantity (last numeric value in line)
    # -----------------------------------------------------
    qty_match = re.findall(r'\d+(?:\.\d+)?', text)
    
    if not qty_match:
        raise ValueError(f"No numeric quantity found: {text}")

    length = float(qty_match[-1])

    # Detect fire cable
    is_fire = bool(re.search(r"(fire|fr|resistant|cei)", text, re.IGNORECASE))

    # -----------------------------------------------------
    # PRIORITY PATTERN: (4X150mm2)
    # Always extract inner X format first
    # -----------------------------------------------------
    pattern_inner_x = (
        r'\(\s*(?P<cores>\d+)\s*[xX]\s*'
        r'(?P<power>\d+(?:\.\d+)?)\s*mm?2?\s*\)'
        r'.*?(?P<length>\d+(?:\.\d+)?)$'
    )
    
    match = re.search(pattern_inner_x, text, re.IGNORECASE)
    if match:
        return {
            "raw_text": text,
            "cores": int(match.group("cores")),
            "power_size": float(match.group("power")),
            "earth_size": None,
            "length": float(match.group("length")),
            "is_fire": is_fire,
            "is_vj": False
        }

    # -----------------------------------------------------
    # VJ EARTH FORMAT: "VJ 120mm LM 75"  => earth cable
    # -----------------------------------------------------
    pattern_vj = r'\bVJ\b\s*(?P<size>\d+(?:\.\d+)?)\s*(?:mm2|mm²|mm)?\b'
    m = re.search(pattern_vj, text, re.IGNORECASE)
    if m:
        return {
            "raw_text": text,
            "cores": 1,
            "power_size": float(m.group("size")),
            "earth_size": None,
            "length": length,
            "is_fire": is_fire,
            "is_vj": True,   # <-- add this flag
        }
    # -----------------------------------------------------
    # NEW FORMAT: Size (2C6) mm2 ML 20
    # -----------------------------------------------------
    pattern_parenthesis = (
        r'\(\s*(?P<cores>\d+)\s*[cC]\s*(?P<power>\d+(?:\.\d+)?)\s*\)'
        r'.*?(?P<length>\d+(?:\.\d+)?)$'
    )

    match = re.search(pattern_parenthesis, text, re.IGNORECASE)
    if match:
        return {
            "raw_text": text,
            "cores": int(match.group("cores")),
            "power_size": float(match.group("power")),
            "earth_size": None,
            "length": float(match.group("length")),
            "is_fire": is_fire,
            "is_vj": False
        }

    # -----------------------------------------------------
    # EXISTING +E FORMAT
    # -----------------------------------------------------
    pattern_plus_e = (
        r'(?P<cores>\d+)\s*[cC]\s*'
        r'(?P<power>\d+(?:\.\d+)?)\s*mm²'
        r'(?:\s*\+\s*E\s*=\s*(?P<earth>\d+(?:\.\d+)?)\s*mm²)?'
        r'.*?(?P<length>\d+(?:\.\d+)?)$'
    )

    match = re.search(pattern_plus_e, text, re.IGNORECASE)
    if match:
        return {
            "raw_text": text,
            "cores": int(match.group("cores")),
            "power_size": float(match.group("power")),
            "earth_size": float(match.group("earth")) if match.group("earth") else None,
            "length": float(match.group("length")),
            "is_fire": is_fire,
            "is_vj": False
        }

    # -----------------------------------------------------
    # SIMPLE 4x6 FORMAT
    # -----------------------------------------------------
    pattern_simple = (
        r'(?P<cores>\d+)\s*[xX]\s*'
        r'(?P<power>\d+(?:\.\d+)?)'
    )

    match = re.search(pattern_simple, text, re.IGNORECASE)
    if match:
        return {
            "raw_text": text,
            "cores": int(match.group("cores")),
            "power_size": float(match.group("power")),
            "earth_size": None,
            "length": length,
            "is_fire": is_fire,
            "is_vj": False
        }

    
    # -----------------------------------------------------
    # SINGLE SIZE FORMAT: 70 mm2 178 lm
    # -----------------------------------------------------
    pattern_single_size = (
        r'(?P<power>\d+(?:\.\d+)?)\s*mm2'
        r'.*?'
        r'(?P<length>\d+(?:\.\d+)?)\s*(?:lm|ml|m)?\s*$'
    )
    
    match = re.search(pattern_single_size, text, re.IGNORECASE)
    if match:
        return {
            "raw_text": text,
            "cores": 1,  # assume single core
            "power_size": float(match.group("power")),
            "earth_size": None,
            "length": float(match.group("length")),
            "is_fire": is_fire,
            "is_vj": False
        }
    # -----------------------------------------------------
    # SC / C FORMAT: 4SC, 240 MR 50  OR  4C, 10 MR 20
    # -----------------------------------------------------
    pattern_sc = re.search(
        r'^\s*(?P<cores>\d+)\s*S?C\s*,\s*'
        r'(?P<power>\d+(?:\.\d+)?)\s*'
        r'(?:MR|ML|M)?\s*'
        r'(?P<length>\d+(?:\.\d+)?)\s*$',
        text,
        re.IGNORECASE
    )
    
    if pattern_sc:
        return {
            "raw_text": text,
            "cores": int(pattern_sc.group("cores")),
            "power_size": float(pattern_sc.group("power")),
            "earth_size": None,
            "length": float(pattern_sc.group("length")),
            "is_fire": is_fire,
            "is_vj": False
        }

    raise ValueError(f"Cannot parse line: {text}")


# =========================================================
# RULES ENGINE
# =========================================================

def round_rolls(length):
    rolls = length / ROLL_LENGTH
    integer_part = int(rolls)
    decimal = rolls - integer_part

    if decimal >= 0.2:
        integer_part += 1

    return max(integer_part, 1)


def power_family(size, cores=None):
    # Special override
    if cores == 4 and size == 35:
        return "NYY"

    if size < 35:
        return "NYM"

    return "NYY"



def build_power_code(cores, size):
    # Single core non-earth handled separately
    if cores == 1:
        return f"CDL-NYA {int(size)}"

    family = power_family(size, cores)

    if family == "NYM":
        if size in (1.5, 2.5):
            return f"CDL-NYM {cores}X{size}RE"
        return f"CDL-NYM {cores}X{int(size)}"

    return f"CDL-NYY {cores}X{int(size)}SM"



def build_earth_code(size, length):
    if size <= 6:
        rolls = round_rolls(length)
        return f"CDL-NYA {int(size)} GN-YL", str(rolls), ""

    return f"CDL-NYA {int(size)} GN-YL--MT", f"{length:.2f}", "m"


# =========================================================
# TRANSFORMATION
# =========================================================

def transform_to_rows(original_text, force_fire=False):
    """
    Returns a list of output rows (dicts) using ONLY these columns:
    - Item
    - Hareb Code
    - Quantity

    Priority order (as per your rules):
    FIRE → CAT6 → NYZ → 3xA+B locked → parse → 5x → +number split → single core → normal power → earth split
    """
    rows = []
    text = (original_text or "").strip()
    # Convert European decimal comma to dot (e.g., 2,5 → 2.5)
    text = re.sub(r'(\d+),(\d+)', r'\1.\2', text)
    if not text:
        return rows

    text_lower = text.lower()

    # -----------------------------------------------------
    # Helper: last numeric value in line = quantity
    # (Used by CAT6 and 3xA+B locked rule pre-parse)
    # -----------------------------------------------------
    def extract_last_number_as_length(s: str) -> float:
        nums = re.findall(r"\d+(?:\.\d+)?", s)
        if not nums:
            return 0.0
        return float(nums[-1])

    # =====================================================
    # 1️⃣ FIRE RULE (Highest Priority)
    # - fire can come from force_fire OR "fire/fr/resistant/cei" in the row itself OR parsed flag
    # =====================================================
    # Note: we still parse for fire rows so we can reuse your existing parsing logic.
    # But we determine fire intent first so it works with section-headers (force_fire=True).
    fire_intent = force_fire or bool(re.search(r"(fire|fr|resistant|cei)", text_lower, re.IGNORECASE))

    if fire_intent:
        data = parse_line(text)  # get cores/size/earth/length where possible

        cores = data["cores"]
        size = data["power_size"]
        earth = data["earth_size"]
        length = data["length"]

        # Re-detect +number inside fire case (e.g., 4x6 + PE 6)
        plus_match = re.search(
            r'(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*\+\s*(?:PE|E)?\s*(\d+(?:\.\d+)?)',
            text,
            re.IGNORECASE
        )
        if plus_match:
            cores = int(plus_match.group(1))
            size = float(plus_match.group(2))
            earth = float(plus_match.group(3))

        rows.append({
            "Item": text,
            "Hareb Code": f"CDL-SFC2XU {cores}X{format_size(size)} --CEI",
            "Quantity": f"{length:.2f}",
        })

        # If fire cable includes earth → split earth with NYA rule
        if earth:
            code, qty, _unit = build_earth_code(earth, length)
            rows.append({
                "Text": text,
                "Item":"item"
                "Hareb Code": code,
                "Quantity": qty,
            })

        return rows

    # =====================================================
    # 2️⃣ CAT6 RULE (No parse needed)
    # =====================================================
    if "cat6" in text_lower:
        length = extract_last_number_as_length(text)
        rolls = length / 305.0
        # Always round UP, min 1
        rolls_int = int(rolls) if float(rolls).is_integer() else int(rolls) + 1
        rolls_int = max(rolls_int, 1)

        rows.append({
            "Text": text,
            "Item":"item"
            "Hareb Code": "NEX-CAT6UTPLSZH-GY",
            "Quantity": str(rolls_int),
        })
        return rows

    # =====================================================
    # 3️⃣ NYZ RULE (Parse needed to get cores/size)
    # =====================================================
    if "nyz" in text_lower:
        data = parse_line(text)
        cores = data["cores"]
        size = data["power_size"]
        length = data["length"]

        rows.append({
            "Text": text,
            "Item":"item"
            "Hareb Code": f"CDL-NYZ {cores}X{format_size(size)}",
            "Quantity": f"{length:.2f}",
        })
        return rows

    # =====================================================
    # 4️⃣ 3xA + B LOCKED RULE (MUST run before normal parsing logic takes over)
    # - Accept comma or plus between A and B
    # - Trigger only if B < A and A > 35
    # =====================================================
    normalized_text = re.sub(r"\s+", " ", text.replace(",", "+"))
    
    pattern_3x_plus = re.search(
        r'3\s*[xX]\s*'
        r'(?P<A>\d+(?:\.\d+)?)\s*'
        r'\+\s*'
        r'(?P<B>\d+(?:\.\d+)?)(?:\s*mm?2)?',
        normalized_text,
        re.IGNORECASE
    )
    
    if pattern_3x_plus:
        A = float(pattern_3x_plus.group("A"))
        B = float(pattern_3x_plus.group("B"))
    
        if B < A and A > 35:
            length = extract_last_number_as_length(text)
            rows.append({
                "Text": text,
                "Item":"item"
                "Hareb Code": f"CDL-NYY 3X{format_size(A)}+{format_size(B)}SM",
                "Quantity": f"{length:.2f}",
            })
            return rows

    # =====================================================
    # From here onward, we parse once and apply remaining rules
    # =====================================================
    data = parse_line(text)

    is_vj = data.get("is_vj", False)
    cores = data["cores"]
    size = data["power_size"]
    earth = data["earth_size"]
    length = data["length"]


    
    # =====================================================
    # 5️⃣ 5X RULE → 4 power + 1 earth (split)
    # =====================================================
    if cores == 5 and earth is None:
        earth = size
        cores = 4

    # =====================================================
    # 6️⃣ +NUMBER SPLIT RULE (4x10+10 etc.)
    # - Also allow PE/E keyword optionally
    # =====================================================
    pattern_plus_number = re.search(
        r'(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*\+\s*(?:PE|E)?\s*(\d+(?:\.\d+)?)',
        text,
        re.IGNORECASE
    )

    if pattern_plus_number:
        cores = int(pattern_plus_number.group(1))
        size = float(pattern_plus_number.group(2))
        earth = float(pattern_plus_number.group(3))

    # =====================================================
    # 7️⃣ SINGLE CORE LOGIC
    # - If green-yellow mentioned → treat as earth rule
    # - Else if another color abbreviation found → CDL-NYA [size] [color]
    # - Else (no color) → treat as earth rule
    # =====================================================
    is_green_yellow = any(k in text_lower for k in ["yellow-green", "green-yellow", "gn-yl", "gy/yl", "g/y"])

    if cores == 1:
        # IMPORTANT: handle Yellow/Green BEFORE normal colors
        if any(k in text_lower for k in ["yellow/green", "yellow-green", "green/yellow", "green-yellow"]):
            code, qty, _ = build_earth_code(size, length)
            rows.append({"Item": text, "Hareb Code": code, "Quantity": qty})
            return rows
        
        color_match = re.search(
            r'\b(red|yellow|black|blue|brown|grey|gray|white|orange|rd|yl|bk|bl|bu|br|gy|wt|or)\b',
            text_lower
        )
        if color_match:
            key = color_match.group(1).lower()
            color_code = COLOR_MAP.get(key, key.upper())
        
            rows.append({
                "Text": text,
                "Item":"item"
                "Hareb Code": f"CDL-NYA {format_size(size)} {color_code}",
                "Quantity": f"{length:.2f}",
            })
            return rows

        # No color → treat as earth (GN-YL rule)
        code, qty, _unit = build_earth_code(size, length)
        rows.append({
            "Item": text,
            "Hareb Code": code,
            "Quantity": qty,
        })
        return rows

    # =====================================================
    # 8️⃣ NORMAL POWER
    # =====================================================
    power_code = build_power_code(cores, size)
    rows.append({
        "Text": text,
        "Item":"item"
        "Hareb Code": power_code,
        "Quantity": f"{length:.2f}",
    })

    # =====================================================
    # 9️⃣ EARTH SPLIT (from +number or 5x)
    # =====================================================
    if earth:
        code, qty, _unit = build_earth_code(earth, length)
        rows.append({
            "Text": text,
            "Item":"item"
            "Hareb Code": code,
            "Quantity": qty,
        })

    return rows



# =========================================================
# EXPORT
# =========================================================

def export_to_excel(input_lines, output_file="Cable_Conversion_Output.xlsx"):
    all_rows = []
    fire_mode = False

    for line in input_lines:
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()

        # -----------------------------------------
        # Detect section change
        # -----------------------------------------
        if is_new_cable_section(line):

            if is_fire_header(line):
                fire_mode = True
            else:
                fire_mode = False

            continue  # skip section headers

        try:
            all_rows.extend(transform_to_rows(line, force_fire=fire_mode))
        except Exception as e:
            print(f"Skipped: {line} | Error: {e}")

    df = pd.DataFrame(all_rows)
    df.to_excel(output_file, index=False)

    print(f"✅ Excel file created: {output_file}")



def convert_text_file(uploaded_file):
    """
    Used by Streamlit.
    Accepts uploaded TXT file and returns DataFrame.
    """

    content = uploaded_file.read().decode("utf-8")
    lines = content.splitlines()

    all_rows = []
    fire_mode = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # -----------------------------------------
        # Detect section change
        # -----------------------------------------
        if is_new_cable_section(line):

            if is_fire_header(line):
                fire_mode = True
            else:
                fire_mode = False

            continue

        try:
            all_rows.extend(transform_to_rows(line, force_fire=fire_mode))
        except Exception as e:
            print(f"Skipped: {line} | Error: {e}")

    df = pd.DataFrame(all_rows)
    return df









































