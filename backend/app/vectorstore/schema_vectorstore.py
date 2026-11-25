"""
Embedding-based schema search - an upgrade over the plain keyword-overlap
narrowing in app.database.schema_loader.relevant_subset() for large
schemas.

Why this matters beyond keyword matching: a question like "show me our
clients in Germany" has zero token overlap with a table literally named
`customers`, so keyword overlap scores it 0 and might drop it from the
prompt entirely on a schema with 200+ tables. TF-IDF still can't know
"clients" means "customers" semantically (that needs a neural embedding -
see OpenAIEmbeddingBackend in embeddings.py for that upgrade path), but it
DOES correctly rank tables by how much of the question's actual vocabulary
appears across their names/columns/FK neighbors, which in practice catches
most of what keyword-overlap misses because the corpus (table/column
names) is short and keyword-dense rather than prose.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.database.introspector import DatabaseSchema, TableInfo
from app.vectorstore.embeddings import EmbeddingBackend, TFIDFEmbeddingBackend
from app.vectorstore.faiss_index import FAISSIndex


def _table_document(table: TableInfo) -> str:
    """Renders one table into the text blob that gets embedded - name,
    column names/types, and FK neighbor table names, so a query matching
    a related table's name still surfaces this one."""
    parts = [table.name, table.name.replace("_", " ")]
    for col in table.columns:
        parts.append(col.name)
        parts.append(col.name.replace("_", " "))
    for fk in table.foreign_keys:
        parts.append(fk.references_table)
    return " ".join(parts)


@dataclass
class ScoredTable:
    table_name: str
    score: float


class SchemaVectorStore:
    """Builds (once per schema version) and queries a vector index over a
    DatabaseSchema's tables. Callers ask "which tables are relevant to
    this question" and get back a ranked list - see search()."""

    def __init__(self, embedding_backend: Optional[EmbeddingBackend] = None):
        self._backend = embedding_backend or TFIDFEmbeddingBackend()
        self._index: Optional[FAISSIndex] = None
        self._built_for_table_count = 0

    def build(self, schema: DatabaseSchema) -> None:
        if not schema.tables:
            self._index = None
            return

        documents = [_table_document(t) for t in schema.tables]
        self._backend.fit(documents)
        vectors = self._backend.embed(documents)

        self._index = FAISSIndex(dimension=vectors.shape[1])
        self._index.add([t.name for t in schema.tables], vectors)
        self._built_for_table_count = len(schema.tables)

    def is_built(self) -> bool:
        return self._index is not None

    def search(self, question: str, k: int = 12) -> List[ScoredTable]:
        if self._index is None or self._index.size == 0:
            return []
        query_vector = self._backend.embed([question])[0]
        results = self._index.search(query_vector, k)
        return [ScoredTable(table_name=name, score=score) for name, score in results]
