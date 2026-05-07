from pymongo import MongoClient
import certifi
from backend.config import MONGO_URI, DB_NAME, COLLECTION_NAME

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
collection = client[DB_NAME][COLLECTION_NAME]


def store_embeddings(chunks, embeddings):
    docs = []
    for chunk, emb in zip(chunks, embeddings):
        docs.append({
            "text": chunk,
            "embedding": emb
        })
    collection.insert_many(docs)


def search_similar(query_embedding, top_k=3):
    pipeline = [
        {
            "$vectorSearch": {
                "queryVector": query_embedding,
                "path": "embedding",
                "numCandidates": 100,
                "limit": top_k,
                "index": "vector_index"
            }
        }
    ]

    results = collection.aggregate(pipeline)
    return [doc["text"] for doc in results]