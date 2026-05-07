import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="RAG Chatbot", layout="wide")

st.title("📄 PDF RAG Chatbot")

# Upload PDF
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    files = {"file": uploaded_file.getvalue()}
    response = requests.post(f"{BACKEND_URL}/upload", files={"file": uploaded_file})
    st.success("PDF uploaded and processed!")

# Chat UI
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

query = st.text_input("Ask a question")

# if st.button("Send"):
#     res = requests.get(f"{BACKEND_URL}/ask", params={"query": query})
#     answer = res.json()["answer"]

#     st.session_state.chat_history.append((query, answer))

if st.button("Send"):
    res = requests.get(f"{BACKEND_URL}/ask", params={"query": query})

    if res.headers.get("content-type", "").startswith("application/json"):
        data = res.json()
        answer = data.get("answer", "No answer found")
    else:
        print("Non-JSON response:", res.text)
        answer = "Error: Backend did not return JSON"

    st.session_state.chat_history.append((query, answer))

# Display chat
for q, a in st.session_state.chat_history:
    st.markdown(f"**You:** {q}")
    st.markdown(f"**Bot:** {a}")