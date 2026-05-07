from fastapi import FastAPI, UploadFile, File
import os

from backend.utils.pdf_loader import load_pdf, chunk_text
from backend.services.embedding_service import get_embedding
from backend.services.vector_store import store_embeddings
from backend.services.rag_pipeline import generate_answer

app = FastAPI()


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    file_path = f"temp_{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    text = load_pdf(file_path)
    chunks = chunk_text(text)

    embeddings = [get_embedding(chunk) for chunk in chunks]

    store_embeddings(chunks, embeddings)

    os.remove(file_path)

    return {"message": "PDF processed successfully"}


# @app.get("/ask")
# def ask_question(query: str):
#     answer = generate_answer(query)
#     return {"answer": answer}

@app.get("/ask")
def ask_question(query: str):
    try:
        answer = generate_answer(query)
        return {"answer": answer}
    except Exception as e:
        print("ERROR in /ask:", e)
        return {"answer": f"Error: {str(e)}"}

@app.get("/")
def home():
    return {"message": "Backend is running"}