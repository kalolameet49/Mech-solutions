import streamlit as st
import tempfile
import os
from deepnest_runner import run_deepnest

st.set_page_config(page_title="ProNester Cloud", layout="wide")

st.title("⚙️ ProNester (Deepnest Powered)")

uploaded_file = st.file_uploader("Upload SVG file", type=["svg"])

if uploaded_file:
    st.success("File uploaded successfully")

    if st.button("🚀 Run Nesting"):
        with st.spinner("Running Deepnest..."):

            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as tmp:
                tmp.write(uploaded_file.getvalue())
                input_path = tmp.name

            # Run Deepnest
            output_path, error = run_deepnest(input_path)

            if error:
                st.error(f"Error: {error}")
            elif output_path and os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    st.download_button(
                        "📥 Download Nested File",
                        f,
                        file_name="nested.svg"
                    )
            else:
                st.error("Deepnest failed")
