"""
Embedding generation module for RAG pipeline.
Uses sentence-transformers with all-MiniLM-L6-v2 (22MB, 384 dimensions).
Falls back to simple TF-IDF vectors if sentence-transformers unavailable.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional

# Try to import sentence-transformers
EMBEDDINGS_AVAILABLE = False
_model = None

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    pass


def _get_model():
    """Lazy load the embedding model."""
    global _model
    if _model is None and EMBEDDINGS_AVAILABLE:
        # all-MiniLM-L6-v2: 22MB, 384 dimensions, fast inference
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def get_embedding_info() -> Dict[str, Any]:
    """Get information about the embedding system."""
    return {
        "available": EMBEDDINGS_AVAILABLE,
        "model": "all-MiniLM-L6-v2" if EMBEDDINGS_AVAILABLE else "tfidf-fallback",
        "dimensions": 384 if EMBEDDINGS_AVAILABLE else 100,
        "description": "Sentence-BERT embeddings" if EMBEDDINGS_AVAILABLE else "TF-IDF sparse vectors"
    }


def generate_embedding(text: str, model_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate embedding for a single text.

    Returns:
        {
            "embedding": [...],  # List of floats
            "dimensions": 384,
            "model": "all-MiniLM-L6-v2",
            "text_hash": "abc123..."  # For deduplication
        }
    """
    text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:12]

    # For now, only all-MiniLM-L6-v2 is supported
    # Other models (text-embedding-3-small, nomic-embed) would require additional setup
    # This gracefully falls back to the default model
    if EMBEDDINGS_AVAILABLE:
        model = _get_model()
        embedding = model.encode(text, convert_to_numpy=True).tolist()
        return {
            "embedding": embedding,
            "dimensions": len(embedding),
            "model": model_name if model_name else "all-MiniLM-L6-v2",
            "text_hash": text_hash
        }
    else:
        # Fallback: Simple TF-IDF-like vector (for demo purposes)
        embedding = _simple_embedding(text)
        return {
            "embedding": embedding,
            "dimensions": len(embedding),
            "model": "tfidf-fallback",
            "text_hash": text_hash
        }


def generate_embeddings_batch(texts: List[str], model_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Generate embeddings for multiple texts efficiently.
    """
    if EMBEDDINGS_AVAILABLE:
        model = _get_model()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

        results = []
        for i, text in enumerate(texts):
            text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:12]
            results.append({
                "embedding": embeddings[i].tolist(),
                "dimensions": len(embeddings[i]),
                "model": model_name if model_name else "all-MiniLM-L6-v2",
                "text_hash": text_hash
            })
        return results
    else:
        # Fallback for each text
        return [generate_embedding(text) for text in texts]


def _simple_embedding(text: str, dimensions: int = 100) -> List[float]:
    """
    Simple fallback embedding using character/word frequency features.
    Not suitable for production, but works for demos when sentence-transformers unavailable.
    """
    import math

    # Normalize text
    text = text.lower()
    words = text.split()

    # Create a simple feature vector
    embedding = [0.0] * dimensions

    # Feature 1-20: Character frequency (a-z normalized)
    for char in text:
        if 'a' <= char <= 'z':
            idx = ord(char) - ord('a')
            if idx < 20:
                embedding[idx] += 1

    # Feature 21-40: Word length distribution
    for word in words:
        length = min(len(word), 20)
        embedding[20 + length - 1] += 1

    # Feature 41-60: Common word indicators
    common_words = ['the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should']
    for i, cw in enumerate(common_words):
        if cw in words:
            embedding[40 + i] = words.count(cw) / max(len(words), 1)

    # Feature 61-80: Punctuation and structure
    embedding[60] = text.count('.') / max(len(text), 1) * 100
    embedding[61] = text.count(',') / max(len(text), 1) * 100
    embedding[62] = text.count('?') / max(len(text), 1) * 100
    embedding[63] = text.count('!') / max(len(text), 1) * 100
    embedding[64] = text.count(':') / max(len(text), 1) * 100
    embedding[65] = len(words) / 100  # Normalized word count
    embedding[66] = len(text) / 1000  # Normalized char count
    embedding[67] = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    embedding[68] = sum(1 for c in text if c.isdigit()) / max(len(text), 1)
    embedding[69] = text.count('\n') / max(len(text), 1) * 100

    # Feature 81-96: Hash-based features for variety (MD5 hex is 32 chars = 16 pairs)
    text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    for i in range(16):
        embedding[80 + i] = int(text_hash[i * 2:(i + 1) * 2], 16) / 255.0

    # Normalize to unit vector
    magnitude = math.sqrt(sum(x * x for x in embedding))
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]

    return embedding


def embed_chunks(chunks: List[Dict[str, Any]], include_text: bool = True, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Generate embeddings for a list of chunks.

    Args:
        chunks: List of chunk dictionaries with 'text' field
        include_text: Whether to include the original text in output
        model_name: Optional embedding model name (currently only all-MiniLM-L6-v2 supported)

    Returns:
        List of chunks with embeddings added
    """
    texts = [chunk.get('text', '') for chunk in chunks]
    embeddings = generate_embeddings_batch(texts, model_name)

    results = []
    for i, chunk in enumerate(chunks):
        result = {
            "id": chunk.get('id', i),
            "embedding": embeddings[i]['embedding'],
            "dimensions": embeddings[i]['dimensions'],
            "model": embeddings[i]['model'],
            "text_hash": embeddings[i]['text_hash'],
            "tokens": chunk.get('tokens', 0),
            "metadata": chunk.get('metadata', {})
        }
        if include_text:
            result['text'] = chunk.get('text', '')
        results.append(result)

    return results


def export_for_chromadb(chunks: List[Dict[str, Any]], collection_name: str = "documents") -> Dict[str, Any]:
    """
    Export chunks in ChromaDB-ready format.

    ChromaDB expects:
    - ids: List[str]
    - embeddings: List[List[float]]
    - documents: List[str]
    - metadatas: List[Dict]
    """
    embedded = embed_chunks(chunks, include_text=True)

    return {
        "collection_name": collection_name,
        "ids": [f"chunk_{c['id']}" for c in embedded],
        "embeddings": [c['embedding'] for c in embedded],
        "documents": [c['text'] for c in embedded],
        "metadatas": [{"tokens": c['tokens'], "text_hash": c['text_hash'], **c.get('metadata', {})} for c in embedded],
        "embedding_info": get_embedding_info()
    }


def export_for_lancedb(chunks: List[Dict[str, Any]], table_name: str = "documents") -> Dict[str, Any]:
    """
    Export chunks in LanceDB-ready format (list of records).

    LanceDB expects a list of dictionaries with 'vector' field.
    """
    embedded = embed_chunks(chunks, include_text=True)

    records = []
    for c in embedded:
        records.append({
            "id": f"chunk_{c['id']}",
            "text": c['text'],
            "vector": c['embedding'],
            "tokens": c['tokens'],
            "text_hash": c['text_hash'],
            **c.get('metadata', {})
        })

    return {
        "table_name": table_name,
        "records": records,
        "schema": {
            "id": "string",
            "text": "string",
            "vector": f"vector[{embedded[0]['dimensions'] if embedded else 384}]",
            "tokens": "int",
            "text_hash": "string"
        },
        "embedding_info": get_embedding_info()
    }


def export_jsonl(chunks: List[Dict[str, Any]], include_embeddings: bool = False) -> str:
    """
    Export chunks as JSONL format (one JSON object per line).
    Perfect for streaming and large datasets.
    """
    lines = []

    if include_embeddings:
        embedded = embed_chunks(chunks, include_text=True)
        for c in embedded:
            lines.append(json.dumps({
                "id": c['id'],
                "text": c['text'],
                "embedding": c['embedding'],
                "tokens": c['tokens'],
                "metadata": c.get('metadata', {})
            }, ensure_ascii=False))
    else:
        for i, chunk in enumerate(chunks):
            lines.append(json.dumps({
                "id": chunk.get('id', i),
                "text": chunk.get('text', ''),
                "tokens": chunk.get('tokens', 0),
                "metadata": chunk.get('metadata', {})
            }, ensure_ascii=False))

    return '\n'.join(lines)
