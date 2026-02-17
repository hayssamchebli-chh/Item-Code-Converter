import re
import pandas as pd

ROLL_LENGTH = 92

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
            "is_fire": is_fire
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
            "is_fire": is_fire
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
            "is_fire": is_fire
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
            "is_fire": is_fire
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
            "is_fire": is_fire
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
    data = parse_line(original_text)
    rows = []

    cores = data["cores"]
    size = data["power_size"]
    earth = data["earth_size"]
    length = data["length"]
    is_fire = data["is_fire"] or force_fire


    text_lower = original_text.lower()

    # =====================================================
    # 1️⃣ FIRE RULE (Highest Priority)
    # =====================================================
    if is_fire:
        # Re-detect +number inside fire case
        plus_match = re.search(
            r'(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)',
            original_text
        )
    
        if plus_match:
            cores = int(plus_match.group(1))
            size = float(plus_match.group(2))
            earth = float(plus_match.group(3))
    
        rows.append({
            "Original Text": original_text,
            "Converted Code":f"CDL-SFC2XU {cores}X{size} --CEI",
            "Quantity": f"{length:.2f}",
            "Unit": "m"
        })
    
        if earth:
            code, qty, unit = build_earth_code(earth, length)
            rows.append({
                "Original Text": original_text,
                "Converted Code": code,
                "Quantity": qty,
                "Unit": unit
            })
    
        return rows
    
    
    # =====================================================
    # 2️⃣ CAT6 RULE
    # =====================================================
    if "cat6" in text_lower:
        rolls = length / 305
        rolls = int(rolls) + (1 if rolls % 1 > 0 else 0)
        rolls = max(rolls, 1)
    
        rows.append({
            "Original Text": original_text,
            "Converted Code": "NEX-CAT6UTPLSZH-GY",
            "Quantity": str(rolls),
            "Unit": ""
        })
        return rows
    
    
    # =====================================================
    # 3️⃣ NYZ RULE
    # =====================================================
    if "nyz" in text_lower:
        rows.append({
            "Original Text": original_text,
            "Converted Code": f"CDL-NYZ {cores}X{int(size)}",
            "Quantity": f"{length:.2f}",
            "Unit": "m"
        })
        return rows


    # =====================================================
    # 4️⃣ 3xA+B LOCKED RULE
    # =====================================================
    pattern_3x_plus = re.search(
        r'\b3\s*[xX]\s*(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\b',
        original_text
    )


    if pattern_3x_plus:
        A = float(pattern_3x_plus.group(1))
        B = float(pattern_3x_plus.group(2))

        if B < A and A > 35:
            rows.append({
                "Original Text": original_text,
                "Converted Code": f"CDL-NYY 3X{int(A)}+{int(B)}SM",
                "Quantity": f"{length:.2f}",
                "Unit": "m"
            })
            return rows

    # =====================================================
    # 5️⃣ 5X RULE → 4 power + 1 earth
    # =====================================================
    if cores == 5 and earth is None:
        earth = size
        cores = 4

    # =====================================================
    # 6️⃣ +NUMBER SPLIT RULE (4x10+10 etc.)
    # =====================================================
    pattern_plus_number = re.search(
        r'(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)',
        original_text
    )

    if pattern_plus_number:
        cores = int(pattern_plus_number.group(1))
        size = float(pattern_plus_number.group(2))
        earth = float(pattern_plus_number.group(3))

    # =====================================================
    # 7️⃣ SINGLE CORE LOGIC
    # =====================================================
    is_green_yellow = any(
        keyword in text_lower
        for keyword in ["yellow-green", "green-yellow", "gn-yl"]
    )

    if cores == 1:
        # Earth
        if is_green_yellow:
            code, qty, unit = build_earth_code(size, length)
            rows.append({
                "Original Text": original_text,
                "Converted Code": code,
                "Quantity": qty,
                "Unit": unit
            })
            return rows

        # Detect other colors
        color_match = re.search(
            r'\b(wt|bk|rd|bl|bu|br|gy|yl|or)\b',
            text_lower
        )

        if color_match:
            color = color_match.group(1).upper()
            rows.append({
                "Original Text": original_text,
                "Converted Code": f"CDL-NYA {int(size)} {color}",
                "Quantity": f"{length:.2f}",
                "Unit": "m"
            })
            return rows

        # No color → treat as earth
        code, qty, unit = build_earth_code(size, length)
        rows.append({
            "Original Text": original_text,
            "Converted Code": code,
            "Quantity": qty,
            "Unit": unit
        })
        return rows

    # =====================================================
    # 8️⃣ NORMAL POWER
    # =====================================================
    power_code = build_power_code(cores, size)

    rows.append({
        "Original Text": original_text,
        "Converted Code": power_code,
        "Quantity": f"{length:.2f}",
        "Unit": "m"
    })

    # =====================================================
    # 9️⃣ EARTH SPLIT (from +number or 5x)
    # =====================================================
    if earth:
        code, qty, unit = build_earth_code(earth, length)
        rows.append({
            "Original Text": original_text,
            "Converted Code": code,
            "Quantity": qty,
            "Unit": unit
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















