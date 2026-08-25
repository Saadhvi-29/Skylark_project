import os
import streamlit as st

# Bridge Streamlit Cloud's secrets into environment variables so the
# existing modules (monday_client, agent, etc.) work unchanged — they
# were written to read from os.environ. Locally (no secrets.toml file),
# st.secrets raises instead of just being empty, so this is skipped and
# your PowerShell $env: variables are used directly instead.
try:
    for key in ["MONDAY_API_KEY", "DEALS_BOARD_ID", "WORK_ORDERS_BOARD_ID", "GROQ_API_KEY", "GROQ_MODEL"]:
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except Exception:
    pass  # no secrets.toml locally — that's fine, env vars are already set

from agent import answer

st.set_page_config(page_title="Skylark BI Agent", page_icon="📊")
st.title("📊 Skylark Drones — BI Agent")
st.caption("Ask about deals and pipeline. Data is pulled live from monday.com, not cached CSVs.")

leadership_mode = st.sidebar.checkbox("Leadership update mode (bullet format)", value=False)
st.sidebar.markdown("---")
st.sidebar.markdown("**Covers:** Deals board + Work Orders board.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("e.g. How's our pipeline looking for energy sector this quarter?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Pulling live data and running the numbers..."):
            try:
                response = answer(prompt, leadership_update=leadership_mode)
            except Exception as e:
                response = f"Something went wrong on that query: {e}"
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response}) 