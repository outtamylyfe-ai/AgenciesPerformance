import streamlit as st

# Read the HTML file (use the correct file name)
with open("components.html", "r", encoding="utf-8") as f:
    html_content = f.read()

# Render it in the app (v1 = version 1, not vl)
st.components.v1.html(html_content, height=900, scrolling=True)
else:
    st.info("Please upload an Excel file to begin.")
