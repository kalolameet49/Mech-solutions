import streamlit as st
from modules.login_ui import login_page
from modules.dashboard_ui import dashboard_page

st.set_page_config(page_title="ProNester SaaS", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    login_page()
else:
    dashboard_page()
