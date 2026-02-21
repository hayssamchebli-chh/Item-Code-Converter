import streamlit as st
import pandas as pd
import io
from converter import transform_to_rows

st.set_page_config(page_title="CDL Cable Converter", layout="wide")

st.title("🔌 CDL Cable Converter")

# Create 2 equal columns
col1, col2 = st.columns(2)

# -----------------------------
# LEFT COLUMN → Standard
# -----------------------------
with col1:
    st.markdown("### 🟢 Standard Cables")
    standard_input = st.text_area(
        "Paste Standard Cable Lines:",
        height=200,
        key="standard_box"
    )

# -----------------------------
# RIGHT COLUMN → Fire
# -----------------------------
with col2:
    st.markdown("### 🔥 Fire Cables")
    fire_input = st.text_area(
        "Paste Fire Cable Lines:",
        height=200,
        key="fire_box"
    )

# Convert button
#st.markdown("---")

if st.button(" Convert", use_container_width=True):

    all_rows = []

    # Standard cables
    if standard_input.strip():
        for line in standard_input.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                all_rows.extend(transform_to_rows(line, force_fire=False))
            except Exception:
                st.warning(f"Skipped (Standard): {line}")

    # Fire cables
    if fire_input.strip():
        for line in fire_input.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                all_rows.extend(transform_to_rows(line, force_fire=True))
            except Exception:
                st.warning(f"Skipped (Fire): {line}")

    if all_rows:
        df = pd.DataFrame(all_rows)
    
        # Keep only required columns
        df = df[["Item", "Converted Code", "Quantity"]]
    
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No valid lines detected.")



