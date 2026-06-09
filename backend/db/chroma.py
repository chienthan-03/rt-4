import chromadb
from backend.config import settings

_client = None
_collection = None

def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = _client.get_or_create_collection(
            name="sounds",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def add_sound_embedding(sound_id: str, document: str, metadata: dict):
    col = get_collection()
    col.add(ids=[sound_id], documents=[document], metadatas=[metadata])

def search_sounds(query: str, top_k: int = 5, where: dict = None) -> list[dict]:
    col = get_collection()
    kwargs = {"query_texts": [query], "n_results": top_k}
    if where:
        kwargs["where"] = where
    results = col.query(**kwargs)
    if not results or not results.get("ids") or len(results["ids"]) == 0:
        return []
    return [
        {"id": results["ids"][0][i], "distance": results["distances"][0][i],
         "metadata": results["metadatas"][0][i]}
        for i in range(len(results["ids"][0]))
    ]
