import streamlit as st
import requests

st.set_page_config(page_title="ProNester Cloud", layout="wide")

st.title("⚙️ ProNester (Cloud Deepnest)")

API_URL = "https://your-api.up.railway.app/nest"

file = st.file_uploader("Upload SVG", type=["svg"])

if file:
    if st.button("🚀 Run Nesting"):

        with st.spinner("Sending to Deepnest API..."):

            files = {"file": file.getvalue()}

            response = requests.post(API_URL, files=files)

            if response.status_code == 200:
                st.download_button(
                    "📥 Download Nested File",
                    response.content,
                    "nested.svg"
                )
            else:
                st.error(response.text)
