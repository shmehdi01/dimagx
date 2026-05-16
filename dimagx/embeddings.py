"""
DimagX Embeddings
Generates vector representations for semantic search.
"""

from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

_model = None

def get_model():
    global _model
    if _model is None:
        # MiniLM is fast, small (80MB) and accurate for code/text search
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def generate_embedding(text: str) -> List[float]:
    """Generate a 384-dimension embedding for the given text."""
    if not text:
        return [0.0] * 384
    model = get_model()
    embedding = model.encode(text)
    return embedding.tolist()

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
