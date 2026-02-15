import streamlit as st
import pandas as pd
import io
from converter import transform_to_rows

st.set_page_config(page_title="CDL Cable Converter", layout="wide")

st.title("🔌 CDL Cable Converter")

st.markdown("Paste your cable lines below (one per line) and click Convert.")

# Text input area
input_text = st.text_area(
    "Paste Cable Text Here:",
    height=250,
    placeholder="Example:\nSize (2C6) mm2 ML 20\nSize (1x4) mm2 Yellow-Green ML 10"
)

# Convert button
if st.button("🚀 Convert"):

    if not input_text.strip():
        st.warning("Please paste some text first.")
    else:
        lines = input_text.splitlines()
        all_rows = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                all_rows.extend(transform_to_rows(line))
            except Exception as e:
                st.error(f"Skipped line: {line} | Error: {e}")

        if all_rows:
            df = pd.DataFrame(all_rows)

            st.success("Conversion completed!")
            st.dataframe(df, use_container_width=True)

            # ✅ Excel export using buffer (correct way)
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)

            st.download_button(
                label="📥 Download Excel",
                data=buffer,
                file_name="Cable_Conversion_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No valid lines were converted.")
