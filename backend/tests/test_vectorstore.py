"""
Tests for the embedding-based schema search (app.vectorstore). Uses the
real TF-IDF backend and a real FAISS index - no mocking, no network - this
is the one embedding backend that's fully offline-testable (see
app/vectorstore/embeddings.py for why OpenAIEmbeddingBackend isn't
exercised here: it needs live network access to api.openai.com).
"""
from __future__ import annotations

from app.database.introspector import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from app.vectorstore import SchemaVectorStore
from app.vectorstore.embeddings import TFIDFEmbeddingBackend
from app.vectorstore.faiss_index import FAISSIndex


def _sample_schema() -> DatabaseSchema:
    return DatabaseSchema(
        engine_name="postgresql",
        database_name="test",
        tables=[
            TableInfo(
                name="customers", schema=None,
                columns=[
                    ColumnInfo("id", "INT", False, None, True),
                    ColumnInfo("name", "TEXT", False, None, False),
                    ColumnInfo("country", "TEXT", True, None, False),
                ],
                primary_key=["id"],
            ),
            TableInfo(
                name="orders", schema=None,
                columns=[
                    ColumnInfo("id", "INT", False, None, True),
                    ColumnInfo("customer_id", "INT", False, None, False),
                    ColumnInfo("amount", "NUMERIC", False, None, False),
                ],
                primary_key=["id"],
                foreign_keys=[ForeignKeyInfo("customer_id", "customers", "id")],
            ),
            TableInfo(
                name="products", schema=None,
                columns=[
                    ColumnInfo("id", "INT", False, None, True),
                    ColumnInfo("title", "TEXT", False, None, False),
                    ColumnInfo("price", "NUMERIC", False, None, False),
                ],
                primary_key=["id"],
            ),
            TableInfo(
                name="employees", schema=None,
                columns=[
                    ColumnInfo("id", "INT", False, None, True),
                    ColumnInfo("name", "TEXT", False, None, False),
                    ColumnInfo("department", "TEXT", False, None, False),
                ],
                primary_key=["id"],
            ),
        ],
    )


class TestFAISSIndex:
    def test_add_and_search_returns_closest_match(self):
        import numpy as np

        index = FAISSIndex(dimension=3)
        index.add(["a", "b", "c"], np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype="float32"))
        results = index.search(np.array([0.9, 0.1, 0], dtype="float32"), k=1)
        assert results[0][0] == "a"

    def test_empty_index_returns_no_results(self):
        index = FAISSIndex(dimension=3)
        import numpy as np
        assert index.search(np.array([1, 0, 0], dtype="float32"), k=5) == []


class TestTFIDFEmbeddingBackend:
    def test_char_ngrams_match_plural_variants(self):
        # This is the specific problem this backend was chosen to solve -
        # word-level TF-IDF would score "customer" vs "customers" as zero
        # overlap; char n-grams should score a real similarity.
        backend = TFIDFEmbeddingBackend()
        backend.fit(["customers id name country", "products id title price"])
        vectors = backend.embed(["how many orders per customer", "customers id name country"])
        similarity = float((vectors[0] * vectors[1]).sum())
        assert similarity > 0.2


class TestSchemaVectorStore:
    def test_builds_index_from_schema(self):
        store = SchemaVectorStore()
        store.build(_sample_schema())
        assert store.is_built()

    def test_search_ranks_relevant_table_first(self):
        store = SchemaVectorStore()
        store.build(_sample_schema())

        results = store.search("employees by department", k=2)
        assert results[0].table_name == "employees"

        results = store.search("total product price", k=2)
        assert results[0].table_name == "products"

    def test_search_surfaces_related_table_despite_wording_mismatch(self):
        # "customer" (singular, in the question) vs "customers" (plural,
        # the table name) - the whole reason this module exists.
        store = SchemaVectorStore()
        store.build(_sample_schema())
        results = store.search("orders grouped by customer", k=4)
        table_names = [r.table_name for r in results if r.score > 0]
        assert "orders" in table_names
        assert "customers" in table_names

    def test_unbuilt_store_returns_empty(self):
        store = SchemaVectorStore()
        assert store.search("anything", k=5) == []


class TestSchemaLoaderVectorStrategy:
    def test_vector_relevant_subset_matches_keyword_when_schema_is_small(self):
        from app.database.schema_loader import vector_relevant_subset

        schema = _sample_schema()  # 4 tables, under any reasonable max_tables
        subset = vector_relevant_subset("conn-test-1", schema, "employees by department", max_tables=12)
        assert set(subset) == {"customers", "orders", "products", "employees"}

    def test_get_relevant_tables_dispatches_on_strategy_setting(self, monkeypatch):
        from app.core.config import settings
        from app.database.schema_loader import get_relevant_tables

        schema = _sample_schema()

        monkeypatch.setattr(settings, "SCHEMA_SEARCH_STRATEGY", "vector")
        vector_result = get_relevant_tables("conn-test-2", schema, "employees by department", max_tables=12)

        monkeypatch.setattr(settings, "SCHEMA_SEARCH_STRATEGY", "keyword")
        keyword_result = get_relevant_tables("conn-test-2", schema, "employees by department", max_tables=12)

        # both strategies return everything here since the schema is small
        # (under max_tables) - the dispatch itself not crashing either way
        # is what this test actually verifies.
        assert set(vector_result) == set(keyword_result) == {"customers", "orders", "products", "employees"}
