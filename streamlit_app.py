import streamlit as st

st.set_page_config(page_title="Sales by Product Type", layout="wide")

# Read the HTML file
try:
    with open("components.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=900, scrolling=True)
except FileNotFoundError:
    st.error("❌ components.html not found. Please place the HTML file in the same directory as this script.")
