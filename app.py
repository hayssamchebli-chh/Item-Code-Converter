import streamlit as st
from converter import convert_text_file

st.title("CDL Cable Converter")

uploaded_file = st.file_uploader("Upload TXT file", type=["txt"])

if uploaded_file:
    df = convert_text_file(uploaded_file)
    st.dataframe(df)

    st.download_button(
        "Download Excel",
        df.to_excel(index=False),
        file_name="converted.xlsx"
    )
