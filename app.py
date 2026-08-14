import streamlit as st  
from dotenv import load_dotenv
 
load_dotenv()  # reads GEMINI_API_KEY from a local .env file

from bot import ask_bot  # noqa: E402  (import after load_dotenv on purpose)

st.set_page_config(page_title="E-commerce Analytics Bot", page_icon="💬")
st.title("E-commerce Analytics Bot")
st.caption("Ask questions about the Amazon India sales data in plain English.")

EXAMPLES = [
    "What's our total revenue?",
    "Which category sells the most?",
    "What's the cancellation rate by state?",
    "Compare average order value: Amazon-fulfilled vs merchant-fulfilled",
    "Which SKUs are almost out of stock?",
]

st.write("Try one of these, or ask your own:")
cols = st.columns(len(EXAMPLES))
clicked = None
for col, ex in zip(cols, EXAMPLES):
    if col.button(ex, use_container_width=True):
        clicked = ex

if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("Ask something about the data...") or clicked

if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer, sql, result = ask_bot(question)
            except Exception as e:
                answer = f"I couldn't answer that one: {e}"
                sql, result = None, None
        st.write(answer)
        if sql is not None:
            with st.expander("Show SQL and raw result"):
                st.code(sql, language="sql")
                st.dataframe(result)

    st.session_state.history.append({"role": "assistant", "content": answer})
