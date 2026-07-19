"""
Thin wrapper around a FAISS flat index for exact nearest-neighbor search
over normalized vectors (inner product == cosine similarity). "Flat"
(brute-force) rather than an approximate index (IVF/HNSW) is the right
choice here: schema search is over dozens-to-low-thousands of tables, not
millions of documents, so exact search is fast enough and simpler/more
correct than tuning an approximate index's recall/speed tradeoff.
"""
from __future__ import annotations

from typing import List, Tuple

import faiss
import numpy as np


class FAISSIndex:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)  # inner product on normalized vectors = cosine similarity
        self._ids: List[str] = []

    def add(self, ids: List[str], vectors: np.ndarray) -> None:
        if vectors.shape[0] != len(ids):
            raise ValueError("Number of vectors must match number of ids")
        if vectors.shape[1] != self.dimension:
            raise ValueError(f"Vector dimension {vectors.shape[1]} doesn't match index dimension {self.dimension}")
        self._index.add(vectors)
        self._ids.extend(ids)

    def search(self, query_vector: np.ndarray, k: int) -> List[Tuple[str, float]]:
        if self._index.ntotal == 0:
            return []
        k = min(k, self._index.ntotal)
        query = query_vector.reshape(1, -1).astype("float32")
        scores, indices = self._index.search(query, k)
        return [
            (self._ids[idx], float(score))
            for idx, score in zip(indices[0], scores[0])
            if idx != -1
        ]

    @property
    def size(self) -> int:
        return self._index.ntotal
