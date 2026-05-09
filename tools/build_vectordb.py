import json
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

CTX_PATH = Path.home() / "wheelchair_ws" / "tools" / "context.json"
DB_PATH = Path.home() / "wheelchair_ws" / "tools" / "chroma_db"

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
client = chromadb.PersistentClient(path=str(DB_PATH))

try:
    client.delete_collection("wheelchair_ctx")
except Exception:
    pass
collection = client.create_collection("wheelchair_ctx")

chunks = json.loads(CTX_PATH.read_text())
texts, metas, ids = [], [], []
for i, c in enumerate(chunks):
    text = f"[{c['type']}] {c.get('name', '')} {c['content']}"
    texts.append(text)
    metas.append({"type": c["type"], "file": c["file"]})
    ids.append(f"chunk_{i}")

embeddings = model.encode(texts, show_progress_bar=True).tolist()
collection.add(embeddings=embeddings, documents=texts, metadatas=metas, ids=ids)
print(f"✅ {len(texts)} chunks indexed → {DB_PATH}")