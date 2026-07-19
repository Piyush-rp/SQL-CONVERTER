"""
Pluggable embedding backends for schema vector search.

TF-IDF is the default: it's a real vector-space-model embedding (cosine
similarity over term-frequency vectors), needs no network access or model
download, and works well for schema search specifically because table/
column names are short, keyword-dense text - exactly what TF-IDF is good
at, unlike long natural-language passages where neural embeddings pull
ahead. It's also why this works fully offline in CI.

An OpenAI-embeddings backend is also provided for deployments that want
neural embeddings (better at synonym matching - e.g. "clients" query
matching a "customers" table) - real code, but note this specific backend
needs network access to OpenAI's API to actually run, which wasn't
available to test live in this build environment (same constraint noted
for Vault in app/core/secrets.py).
"""
from __future__ import annotations

from typing import List, Protocol

import numpy as np


class EmbeddingBackend(Protocol):
    def fit(self, corpus: List[str]) -> None: ...
    def embed(self, texts: List[str]) -> np.ndarray: ...
    @property
    def dimension(self) -> int: ...


class TFIDFEmbeddingBackend:
    """Default backend - scikit-learn TF-IDF over character n-grams (not
    word tokens). This matters specifically for schema search: table/column
    names are short identifiers, and a question about "customer" should
    still match a table named "customers" - word-level TF-IDF treats those
    as entirely different tokens (zero overlap), while character n-grams
    (3-5 chars) share most of their substrings and score a real similarity.
    Vectors are L2-normalized so inner product == cosine similarity (what
    FAISSIndex assumes)."""

    def __init__(self, max_features: int = 4096):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            max_features=max_features,
            analyzer="char_wb",
            ngram_range=(3, 5),
            lowercase=True,
        )
        self._fitted = False

    def fit(self, corpus: List[str]) -> None:
        self._vectorizer.fit(corpus)
        self._fitted = True

    def embed(self, texts: List[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("TFIDFEmbeddingBackend.fit() must be called before embed()")
        matrix = self._vectorizer.transform(texts).toarray().astype("float32")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # avoid div-by-zero for empty/all-stopword text
        return matrix / norms

    @property
    def dimension(self) -> int:
        return len(self._vectorizer.vocabulary_) if self._fitted else 0


class OpenAIEmbeddingBackend:
    """Neural embedding backend via OpenAI's embeddings API. Needs
    OPENAI_API_KEY and network access to api.openai.com - not exercised by
    the test suite in this repo for that reason (see
    tests/test_vectorstore.py for what IS tested: the TF-IDF path, live)."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._dimension = 1536 if "small" in model else 3072

    def fit(self, corpus: List[str]) -> None:
        pass  # nothing to fit - the model is pretrained

    def embed(self, texts: List[str]) -> np.ndarray:
        response = self._client.embeddings.create(model=self._model, input=texts)
        vectors = np.array([d.embedding for d in response.data], dtype="float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    @property
    def dimension(self) -> int:
        return self._dimension
