import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # loads .env for local runs; Streamlit Cloud uses its Secrets box instead


def get_secret(name: str, default=None):
    """Read a value from Streamlit secrets (cloud) or environment variables (local)."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)
