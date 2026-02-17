import re
import pandas as pd


# =========================================================
# PARSER
# =========================================================
def parse_line(text: str):
    text = text.strip()

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
        r'.*?'
        r'(?P<length>\d+(?:\.\d+)?)\s*(?:lm|ml|m)?\s*$'
    )

    match = re.search(pattern_simple, text, re.IGNORECASE)
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
# UPDATED RULE ENGINE (FINAL SYSTEM)
# =========================================================

ROLL_LENGTH = 92
CAT6_ROLL = 305


def round_rolls(length, base):
    rolls = length / base
    integer_part = int(rolls)
    decimal = rolls - integer_part

    if decimal >= 0.2:
        integer_part += 1

    return max(integer_part, 1)


# =========================================================
# POWER FAMILY
# =========================================================

def power_family(cores, size):
    # Special override
    if cores == 4 and size == 35:
        return "NYY"

    if size < 35:
        return "NYM"

    return "NYY"


# =========================================================
# BUILD POWER CODE
# =========================================================

def build_power_code(cores, size):
    family = power_family(cores, size)

    if family == "NYM":
        if size in (1.5, 2.5):
            return f"CDL-NYM {cores}X{size}RE"
        return f"CDL-NYM {cores}X{int(size)}"

    return f"CDL-NYY {cores}X{int(size)}SM"


# =========================================================
# EARTH CODE
# =========================================================

def build_earth_code(size, length):
    if size <= 6:
        rolls = round_rolls(length, ROLL_LENGTH)
        return f"CDL-NYA {int(size)} GN-YL", str(rolls), ""

    return f"CDL-NYA {int(size)} GN-YL--MT", f"{length:.2f}", "m"


# =========================================================
# TRANSFORMATION (UPDATED PRIORITY)
# =========================================================

def transform_to_rows(original_text):
    text_lower = original_text.lower()
    rows = []

    # =====================================================
    # 1️⃣ FIRE CHECK
    # =====================================================
    is_fire = bool(re.search(r"(fire|fr|resistant|cei)", original_text, re.IGNORECASE))
    if is_fire:
        data = parse_line(original_text)
        cores = data["cores"]
        size = data["power_size"]
        length = data["length"]

        rows.append({
            "Original Text": original_text,
            "Converted Code": f"CDL-SFC2XU {cores}X{int(size)} --CEI",
            "Quantity": f"{length:.2f}",
            "Unit": "m"
        })

        return rows

    # =====================================================
    # 2️⃣ CAT6
    # =====================================================
    if "cat6" in text_lower:
        data = parse_line(original_text)
        length = data["length"]
        rolls = round_rolls(length, CAT6_ROLL)

        rows.append({
            "Original Text": original_text,
            "Converted Code": "NEX-CAT6UTPLSZH-GY",
            "Quantity": str(rolls),
            "Unit": ""
        })
        return rows

    # =====================================================
    # 3️⃣ NYZ
    # =====================================================
    if "nyz" in text_lower:
        data = parse_line(original_text)
        cores = data["cores"]
        size = data["power_size"]
        length = data["length"]

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
    match_combined = re.search(r'3\s*[xX]\s*(\d+)\s*\+\s*(\d+)', original_text)
    if match_combined:
        A = float(match_combined.group(1))
        B = float(match_combined.group(2))

        if A > 35 and B < A:
            data = parse_line(original_text)
            length = data["length"]

            rows.append({
                "Original Text": original_text,
                "Converted Code": f"CDL-NYY 3X{int(A)}+{int(B)}SM",
                "Quantity": f"{length:.2f}",
                "Unit": "m"
            })
            return rows

    # =====================================================
    # NORMAL PARSE
    # =====================================================
    data = parse_line(original_text)
    cores = data["cores"]
    size = data["power_size"]
    earth = data["earth_size"]
    length = data["length"]

    # =====================================================
    # 5️⃣ 5X RULE
    # =====================================================
    if cores == 5 and earth is None:
        earth = size
        cores = 4

    # =====================================================
    # 6️⃣ +E SPLIT RULE
    # =====================================================
    power_code = build_power_code(cores, size)

    rows.append({
        "Original Text": original_text,
        "Converted Code": power_code,
        "Quantity": f"{length:.2f}",
        "Unit": "m"
    })

    if earth:
        earth_code, qty, unit = build_earth_code(earth, length)

        rows.append({
            "Original Text": original_text,
            "Converted Code": earth_code,
            "Quantity": qty,
            "Unit": unit
        })

    return rows


    # =====================================================
    # SINGLE CORE EARTH (Green-Yellow)
    # =====================================================
    if cores == 1 and is_green_yellow:
        code, qty, unit = build_earth_code(size, length)

        rows.append({
            "Original Text": original_text,
            "Converted Code": code,
            "Quantity": qty,
            "Unit": unit
        })

        return rows

    # =====================================================
    # NORMAL POWER
    # =====================================================
    power_code = build_power_code(cores, size)

    rows.append({
        "Original Text": original_text,
        "Converted Code": power_code,
        "Quantity": f"{length:.2f}",
        "Unit": "m"
    })

    # =====================================================
    # EARTH (+E rule)
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

    for line in input_lines:
        line = line.strip()
        if not line:
            continue

        try:
            all_rows.extend(transform_to_rows(line))
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

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            all_rows.extend(transform_to_rows(line))
        except Exception as e:
            print(f"Skipped: {line} | Error: {e}")

    df = pd.DataFrame(all_rows)
    return df




