import streamlit as st
import pandas as pd
from converter import convert_text_file

st.title("CDL Cable Converter")

uploaded_file = st.file_uploader("Upload TXT")

if uploaded_file:
    output_df = convert_text_file(uploaded_file)
    st.dataframe(output_df)
