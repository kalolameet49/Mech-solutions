import streamlit as st
import requests

st.set_page_config(page_title="ProNester Cloud", layout="wide")

st.title("⚙️ ProNester (Deepnest Engine)")

API_URL = "http://localhost:8000/nest"

uploaded_file = st.file_uploader("Upload SVG", type=["svg"])

if uploaded_file:
    st.success("File uploaded")

    if st.button("🚀 Run Nesting"):
        with st.spinner("Processing..."):

            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue())
            }

            res = requests.post(API_URL, files=files)

            if res.status_code == 200:
                st.download_button(
                    "📥 Download Nested File",
                    res.content,
                    file_name="nested.svg"
                )
            else:
                st.error("Failed to process")
