# 📄 PDF RAG Chatbot

A full-stack **Retrieval-Augmented Generation (RAG)** chatbot that lets users upload PDF documents and ask questions about their content. The system extracts text from PDFs, chunks it, generates vector embeddings, stores them in MongoDB Atlas, and uses semantic search + an LLM to answer user queries grounded in the uploaded documents.

---

## 📑 Table of Contents

- [Architecture Overview](#architecture-overview)
- [End-to-End Pipeline Flow](#end-to-end-pipeline-flow)
  - [Phase 1: Document Upload & Ingestion](#phase-1-document-upload--ingestion)
  - [Phase 2: Question Answering & Retrieval](#phase-2-question-answering--retrieval)
- [Models Used & Why](#models-used--why)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [File-by-File Breakdown](#file-by-file-breakdown)
- [MongoDB Atlas Vector Search Setup](#mongodb-atlas-vector-search-setup)
- [Environment Variables](#environment-variables)
- [Requirements](#requirements)
- [Installation & Setup](#installation--setup)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)

---

## Architecture Overview

```
┌─────────────────────┐         ┌─────────────────────────────────────────────┐
│                     │  HTTP   │                 BACKEND                     │
│   FRONTEND          │ ◄─────►│          (FastAPI - Port 8000)              │
│   (Streamlit)       │         │                                             │
│   Port 8501         │         │  ┌───────────┐  ┌──────────────────────┐   │
│                     │         │  │ PDF Loader │  │ Embedding Service    │   │
│  • Upload PDF       │         │  │ (PyMuPDF)  │──│ (all-MiniLM-L6-v2)  │   │
│  • Ask Questions    │         │  └───────────┘  └──────────┬───────────┘   │
│  • View Chat        │         │                            │               │
│                     │         │  ┌─────────────────────────▼─────────┐     │
└─────────────────────┘         │  │      MongoDB Atlas Vector Store   │     │
                                │  │      (stores text + embeddings)   │     │
                                │  └─────────────────────────┬─────────┘     │
                                │                            │               │
                                │  ┌─────────────────────────▼─────────┐     │
                                │  │         RAG Pipeline               │     │
                                │  │  (Retrieve context → Build prompt)│     │
                                │  └─────────────────────────┬─────────┘     │
                                │                            │               │
                                │  ┌─────────────────────────▼─────────┐     │
                                │  │         LLM Service               │     │
                                │  │  (OpenRouter → Nemotron Nano 9B)  │     │
                                │  └───────────────────────────────────┘     │
                                └─────────────────────────────────────────────┘
```

---

## End-to-End Pipeline Flow

### Phase 1: Document Upload & Ingestion

This is what happens when a user uploads a PDF from the frontend:

```
User uploads PDF ──► Streamlit sends file to /upload ──► FastAPI receives file
       │
       ▼
 1. Save PDF temporarily on disk
       │
       ▼
 2. Extract text from PDF (PyMuPDF / fitz)
    └── Reads every page and concatenates all text
       │
       ▼
 3. Chunk the text into smaller pieces
    └── Splits text into chunks of 500 words each
       │
       ▼
 4. Generate embeddings for each chunk
    └── Uses all-MiniLM-L6-v2 model (384-dimensional vectors)
       │
       ▼
 5. Store chunks + embeddings in MongoDB Atlas
    └── Each document = { "text": "chunk text...", "embedding": [0.12, -0.03, ...] }
       │
       ▼
 6. Delete temporary PDF file from disk
       │
       ▼
 7. Return success response to frontend
```

#### Step-by-Step Detail:

**Step 1 — File Received by Backend (`backend/main.py`)**
- The frontend sends the PDF file via a `POST /upload` request.
- FastAPI's `UploadFile` handler receives the file and saves it temporarily as `temp_<filename>.pdf` on disk.

**Step 2 — Text Extraction (`backend/utils/pdf_loader.py` → `load_pdf()`)**
- Uses **PyMuPDF** (imported as `fitz`) to open the PDF.
- Iterates through every page and calls `page.get_text()` to extract raw text.
- Returns the full concatenated text string.

**Step 3 — Text Chunking (`backend/utils/pdf_loader.py` → `chunk_text()`)**
- Takes the full extracted text and splits it by whitespace into individual words.
- Groups every **500 words** into one chunk.
- Returns a list of text chunks (e.g., a 2000-word document → 4 chunks).
- **Why chunk?** LLMs have token limits and embeddings work better on smaller, focused text passages rather than entire documents.

**Step 4 — Embedding Generation (`backend/services/embedding_service.py`)**
- Each chunk is passed to the **`sentence-transformers/all-MiniLM-L6-v2`** model.
- The model converts each text chunk into a **384-dimensional float vector**.
- The vector is converted to a Python list using `.tolist()`.
- **Why this model?** See [Models Used & Why](#models-used--why) section.

**Step 5 — Storage in MongoDB (`backend/services/vector_store.py` → `store_embeddings()`)**
- For each chunk, a document is created: `{ "text": "<chunk>", "embedding": [<384 floats>] }`.
- All documents are inserted into MongoDB Atlas using `insert_many()`.
- The collection has a **Vector Search Index** configured (named `vector_index`) to enable semantic similarity search.

**Step 6 — Cleanup**
- The temporary PDF file is deleted from disk using `os.remove()`.

---

### Phase 2: Question Answering & Retrieval

This is what happens when a user asks a question:

```
User types question ──► Streamlit sends query to /ask ──► FastAPI receives query
       │
       ▼
 1. Convert user's question into an embedding
    └── Same all-MiniLM-L6-v2 model used during ingestion
       │
       ▼
 2. Vector search in MongoDB Atlas
    └── $vectorSearch finds top 3 most similar chunks
       │
       ▼
 3. Build a prompt with retrieved context
    └── "Answer ONLY from the context below: <chunks> Question: <query>"
       │
       ▼
 4. Send prompt to LLM via OpenRouter API
    └── nvidia/nemotron-nano-9b-v2:free model generates answer
       │
       ▼
 5. Return LLM's answer to frontend
       │
       ▼
 6. Display answer in Streamlit chat UI
```

#### Step-by-Step Detail:

**Step 1 — Query Embedding (`backend/services/embedding_service.py`)**
- The user's question is converted to a 384-dimensional vector using the **same** `all-MiniLM-L6-v2` model.
- Using the same model for both ingestion and querying ensures vectors are in the same semantic space.

**Step 2 — Vector Similarity Search (`backend/services/vector_store.py` → `search_similar()`)**
- Uses MongoDB Atlas **`$vectorSearch`** aggregation pipeline.
- Searches the `vector_index` on the `embedding` field.
- Evaluates 100 candidates (`numCandidates: 100`) and returns the **top 3** most semantically similar chunks (`limit: 3`).
- Returns only the `text` field from matched documents.

**Step 3 — Prompt Construction (`backend/services/rag_pipeline.py`)**
- The retrieved chunks are joined with newlines into a `context` string.
- A prompt is built instructing the LLM to answer **only** from the provided context:
  ```
  You are a helpful AI assistant.
  Answer ONLY from the context below.

  Context:
  <retrieved chunks>

  Question:
  <user's question>

  Answer:
  ```

**Step 4 — LLM Response (`backend/services/llm_service.py`)**
- The prompt is sent to **OpenRouter API** (`https://openrouter.ai/api/v1/chat/completions`).
- Model used: **`nvidia/nemotron-nano-9b-v2:free`**.
- The response is parsed and the generated answer text is extracted from `result["choices"][0]["message"]["content"]`.
- Includes error handling for API failures (checks for `choices` key in response).

**Step 5–6 — Display**
- The answer is returned as JSON `{"answer": "..."}` to the frontend.
- Streamlit appends the Q&A pair to `session_state.chat_history` and displays it.

---

## Models Used & Why

| Model | Purpose | Provider | Why This Model? |
|-------|---------|----------|-----------------|
| **`sentence-transformers/all-MiniLM-L6-v2`** | Text Embedding (converting text → vectors) | HuggingFace / Sentence-Transformers | **Free & local** — runs entirely on your machine with no API costs. Produces **384-dimensional** vectors which are compact and fast. Excellent quality for semantic similarity tasks. Lightweight (~80MB) and fast inference. One of the most popular embedding models in the open-source community. |
| **`nvidia/nemotron-nano-9b-v2:free`** | LLM for answer generation | OpenRouter (NVIDIA) | **Free tier** available on OpenRouter — no API costs. 9B parameter model offers a good balance between quality and speed. Strong instruction-following capabilities for Q&A tasks. Produces coherent, contextual answers from the provided document chunks. |
| **PyMuPDF (fitz)** | PDF text extraction | Open-source library | **Fast and accurate** PDF parsing. Handles complex PDF layouts well. Extracts clean text without needing OCR for text-based PDFs. Lightweight with no external dependencies. |

### Embedding Model Deep Dive: `all-MiniLM-L6-v2`

- **Architecture**: Based on Microsoft's MiniLM (distilled from a larger transformer)
- **Output Dimensions**: 384 floats per text input
- **Max Input Length**: 256 word-pieces (tokens)
- **Speed**: ~14,000 sentences/sec on GPU, ~300 sentences/sec on CPU
- **Use Case**: Semantic search, clustering, sentence similarity
- **Why not OpenAI embeddings?** OpenAI's `text-embedding-ada-002` requires a paid API key. This model is **completely free** and runs locally.

### LLM Deep Dive: `nvidia/nemotron-nano-9b-v2`

- **Parameters**: 9 billion
- **Access**: Via OpenRouter API (free tier)
- **Strengths**: Good at instruction following, Q&A, and summarization
- **Why via OpenRouter?** OpenRouter provides a unified API to access multiple LLMs. The free tier allows usage without billing setup.
- **Why not run locally?** A 9B model requires significant GPU VRAM to run locally. Using the API offloads this computation.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit | Web UI for PDF upload and chat |
| **Backend API** | FastAPI | REST API server |
| **Server** | Uvicorn | ASGI server for FastAPI |
| **PDF Parsing** | PyMuPDF (fitz) | Extract text from PDF files |
| **Embeddings** | Sentence-Transformers | Convert text to vector embeddings |
| **Vector Database** | MongoDB Atlas | Store embeddings + vector similarity search |
| **LLM Gateway** | OpenRouter API | Access to free LLM models |
| **LLM Model** | NVIDIA Nemotron Nano 9B v2 | Generate answers from context |
| **Config** | python-dotenv | Manage environment variables |
| **TLS** | certifi | SSL certificates for MongoDB connection |

---

## Folder Structure

```
simple-rag-chatbot/
│
├── .env                          # Environment variables (API keys, DB URI) — NOT committed to git
├── .gitignore                    # Ignores .venv, __pycache__, .env
├── requirements.txt              # Python dependencies
├── README.md                     # This file
│
├── backend/                      # FastAPI backend
│   ├── main.py                   # API endpoints (/upload, /ask, /)
│   ├── config.py                 # Loads environment variables
│   │
│   ├── services/                 # Core business logic
│   │   ├── embedding_service.py  # Text → vector embedding conversion
│   │   ├── llm_service.py        # OpenRouter LLM API integration
│   │   ├── rag_pipeline.py       # Orchestrates retrieval + generation
│   │   └── vector_store.py       # MongoDB Atlas vector storage & search
│   │
│   └── utils/                    # Utility functions
│       └── pdf_loader.py         # PDF text extraction & chunking
│
└── frontend/                     # Streamlit frontend
    └── app.py                    # Chat UI with PDF upload
```

---

## File-by-File Breakdown

### `backend/main.py` — API Server
The entry point of the backend. Defines three FastAPI endpoints:
- **`POST /upload`** — Receives a PDF file, extracts text, chunks it, generates embeddings, stores in MongoDB, then cleans up the temp file.
- **`GET /ask?query=...`** — Takes a user question, runs the full RAG pipeline (embed → search → prompt → LLM), returns the answer.
- **`GET /`** — Health check endpoint returning `{"message": "Backend is running"}`.

### `backend/config.py` — Configuration
Loads environment variables from the `.env` file using `python-dotenv`:
- `OPENROUTER_API_KEY` — API key for OpenRouter LLM access
- `MONGO_URI` — MongoDB Atlas connection string
- `DB_NAME` — Database name (default: `rag_db`)
- `COLLECTION_NAME` — Collection name (default: `documents`)

### `backend/utils/pdf_loader.py` — PDF Processing
Contains two functions:
- **`load_pdf(file_path)`** — Opens a PDF with PyMuPDF, extracts text from all pages, returns concatenated text.
- **`chunk_text(text, chunk_size=500)`** — Splits text into chunks of 500 words each. This ensures each chunk is small enough for the embedding model and focused enough for accurate retrieval.

### `backend/services/embedding_service.py` — Embedding Generation
- Loads the **`sentence-transformers/all-MiniLM-L6-v2`** model once at module level (singleton pattern).
- **`get_embedding(text)`** — Encodes a text string into a 384-dimensional vector and returns it as a Python list.

### `backend/services/vector_store.py` — MongoDB Vector Store
Manages all database operations:
- Connects to MongoDB Atlas using `pymongo` with TLS certificates via `certifi`.
- **`store_embeddings(chunks, embeddings)`** — Inserts chunk-embedding pairs as documents into the `documents` collection.
- **`search_similar(query_embedding, top_k=3)`** — Uses MongoDB's `$vectorSearch` aggregation to find the top 3 most semantically similar document chunks. Evaluates 100 candidates for accuracy.

### `backend/services/rag_pipeline.py` — RAG Orchestrator
The core pipeline that ties everything together:
- **`generate_answer(query)`** — Embeds the query → searches for similar chunks → builds a context-grounded prompt → sends to LLM → returns the answer.

### `backend/services/llm_service.py` — LLM Integration
Handles communication with the OpenRouter API:
- **`get_response(prompt)`** — Sends the prompt to `nvidia/nemotron-nano-9b-v2:free` via OpenRouter's chat completions endpoint. Includes error handling that checks for the `choices` key and logs API errors.

### `frontend/app.py` — Streamlit UI
The user-facing web interface:
- **PDF Upload** — File uploader widget that sends the PDF to the backend's `/upload` endpoint.
- **Chat Input** — Text input + Send button that queries the `/ask` endpoint.
- **Chat History** — Maintains conversation history in `st.session_state` and displays all Q&A pairs.

---

## MongoDB Atlas Vector Search Setup

For the `$vectorSearch` to work, you must create a **Vector Search Index** in MongoDB Atlas:

1. Go to your MongoDB Atlas cluster.
2. Navigate to **Atlas Search** → **Create Search Index**.
3. Select **JSON Editor** and use this configuration:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    }
  ]
}
```

4. Set the **index name** to `vector_index`.
5. Select the database `rag_db` and collection `documents`.
6. Click **Create Search Index**.

> **Note:** The `numDimensions` is `384` because the `all-MiniLM-L6-v2` model produces 384-dimensional vectors. The `cosine` similarity metric works best for sentence-transformer embeddings.

---

## Environment Variables

Create a `.env` file in the project root with:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
MONGO_URI=your_mongodb_atlas_connection_string_here
DB_NAME=rag_db
COLLECTION_NAME=documents
```

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | Your API key from [OpenRouter](https://openrouter.ai/) — required for LLM access |
| `MONGO_URI` | MongoDB Atlas connection string (get from Atlas → Connect → Drivers) |
| `DB_NAME` | Name of the MongoDB database to use |
| `COLLECTION_NAME` | Name of the collection to store document chunks & embeddings |

---

## Requirements

All Python dependencies listed in `requirements.txt`:

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | latest | Backend REST API framework |
| `uvicorn` | latest | ASGI server to run FastAPI |
| `pymongo` | latest | MongoDB driver for Python |
| `python-dotenv` | latest | Load `.env` file variables |
| `sentence-transformers` | latest | Embedding model (`all-MiniLM-L6-v2`) |
| `streamlit` | latest | Frontend web UI framework |
| `requests` | latest | HTTP client (frontend → backend, backend → OpenRouter) |
| `pymupdf` | latest | PDF text extraction (imported as `fitz`) |
| `numpy` | latest | Numerical operations (dependency of sentence-transformers) |
| `certifi` | latest | SSL/TLS certificates for secure MongoDB Atlas connection |

---

## Installation & Setup

### Prerequisites
- Python 3.9 or higher
- MongoDB Atlas account (free tier works)
- OpenRouter API key (free tier available)

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/simple-rag-chatbot.git
   cd simple-rag-chatbot
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   - Create a `.env` file in the project root (see [Environment Variables](#environment-variables) section).

5. **Set up MongoDB Atlas Vector Search Index**
   - Follow the steps in [MongoDB Atlas Vector Search Setup](#mongodb-atlas-vector-search-setup).

---

## Running the Application

You need **two terminals** — one for the backend and one for the frontend.

### Terminal 1 — Backend (FastAPI)
```bash
uvicorn backend.main:app --reload
```
Backend runs at: `http://127.0.0.1:8000`

### Terminal 2 — Frontend (Streamlit)
```bash
streamlit run frontend/app.py
```
Frontend runs at: `http://localhost:8501`

### Usage
1. Open the Streamlit UI at `http://localhost:8501`.
2. Upload a PDF file using the file uploader.
3. Wait for the "PDF uploaded and processed!" success message.
4. Type your question in the text input and click **Send**.
5. The bot will answer based on the content of your uploaded PDF.

---

## API Endpoints

| Method | Endpoint | Description | Request | Response |
|--------|----------|-------------|---------|----------|
| `GET` | `/` | Health check | — | `{"message": "Backend is running"}` |
| `POST` | `/upload` | Upload and process a PDF | `multipart/form-data` with `file` field | `{"message": "PDF processed successfully"}` |
| `GET` | `/ask` | Ask a question | Query param: `?query=your question` | `{"answer": "LLM generated answer"}` |

---

## Complete Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DOCUMENT INGESTION                           │
│                                                                      │
│  PDF File ──► PyMuPDF ──► Raw Text ──► 500-word Chunks              │
│                                            │                         │
│                                            ▼                         │
│                                   all-MiniLM-L6-v2                  │
│                                   (384-dim vectors)                  │
│                                            │                         │
│                                            ▼                         │
│                               MongoDB Atlas Collection              │
│                          ┌─────────────────────────────┐            │
│                          │ { text: "...", embedding: [] }│            │
│                          │ { text: "...", embedding: [] }│            │
│                          │ { text: "...", embedding: [] }│            │
│                          └─────────────────────────────┘            │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                       QUESTION ANSWERING                            │
│                                                                      │
│  User Question ──► all-MiniLM-L6-v2 ──► Query Vector (384-dim)      │
│                                              │                       │
│                                              ▼                       │
│                                    $vectorSearch in MongoDB          │
│                                    (cosine similarity, top 3)        │
│                                              │                       │
│                                              ▼                       │
│                                    Retrieved Text Chunks             │
│                                              │                       │
│                                              ▼                       │
│                                    Prompt = Context + Question       │
│                                              │                       │
│                                              ▼                       │
│                                    OpenRouter API                    │
│                                    (Nemotron Nano 9B)                │
│                                              │                       │
│                                              ▼                       │
│                                    Generated Answer ──► User         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## License

This project is for educational and personal use.
