import streamlit as st
import pandas as pd
import io
from converter import transform_to_rows

st.set_page_config(page_title="CDL Cable Converter", layout="wide")

import streamlit as st

st.title("🔌 CDL Cable Converter")

st.markdown("### 🟢 Standard Cable Conversion")
standard_input = st.text_area(
    "Paste Standard Cable Lines Here:",
    height=200,
    key="standard_box"
)

st.markdown("### 🔥 Fire Cable Conversion")
fire_input = st.text_area(
    "Paste Fire Cable Lines Here:",
    height=200,
    key="fire_box"
)


# Convert button
if st.button("Convert"):

    all_rows = []

    # -----------------------------
    # STANDARD CABLES
    # -----------------------------
    if standard_input.strip():
        standard_lines = standard_input.splitlines()

        for line in standard_lines:
            line = line.strip()
            if not line:
                continue
            try:
                all_rows.extend(transform_to_rows(line, force_fire=False))
            except Exception as e:
                st.warning(f"Skipped (Standard): {line}")

    # -----------------------------
    # FIRE CABLES (Force Fire)
    # -----------------------------
    if fire_input.strip():
        fire_lines = fire_input.splitlines()

        for line in fire_lines:
            line = line.strip()
            if not line:
                continue
            try:
                all_rows.extend(transform_to_rows(line, force_fire=True))
            except Exception as e:
                st.warning(f"Skipped (Fire): {line}")

    # -----------------------------
    # Output
    # -----------------------------
    if all_rows:
        df = pd.DataFrame(all_rows)
        st.dataframe(df)

        st.download_button(
            "⬇ Download Excel",
            df.to_csv(index=False),
            file_name="Cable_Conversion_Output.csv",
            mime="text/csv"
        )
    else:
        st.info("No valid lines detected.")
