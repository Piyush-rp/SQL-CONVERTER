from app.database.connector import ConnectionConfig, DatabaseConnector
from app.database.introspector import SchemaIntrospector
from app.database.relationship_builder import RelationshipBuilder
from app.database.schema_loader import relevant_subset
from app.database.schema_serializer import serialize_for_llm
from app.models.connection import DBEngine


def _connector_for(path):
    return DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=path))


def test_connector_connects_and_tests_ok(target_db_path):
    connector = _connector_for(target_db_path)
    assert connector.test_connection() is True


def test_introspection_finds_tables_and_columns(target_db_path):
    connector = _connector_for(target_db_path)
    schema = SchemaIntrospector(connector.engine).introspect()
    assert set(schema.table_names()) == {"customers", "orders"}

    customers = schema.get_table("customers")
    assert {c.name for c in customers.columns} == {"id", "name", "country"}
    assert customers.primary_key == ["id"]


def test_foreign_keys_detected(target_db_path):
    connector = _connector_for(target_db_path)
    schema = SchemaIntrospector(connector.engine).introspect()
    orders = schema.get_table("orders")
    assert len(orders.foreign_keys) == 1
    assert orders.foreign_keys[0].references_table == "customers"


def test_relationship_builder_produces_join_hint(target_db_path):
    connector = _connector_for(target_db_path)
    schema = SchemaIntrospector(connector.engine).introspect()
    rels = RelationshipBuilder.build(schema)
    assert any(r.as_join_hint() == "orders.customer_id = customers.id" for r in rels)


def test_schema_serialization_includes_fk_hint(target_db_path):
    connector = _connector_for(target_db_path)
    schema = SchemaIntrospector(connector.engine).introspect()
    text = serialize_for_llm(schema)
    assert "TABLE customers" in text
    assert "orders.customer_id -> customers.id" in text


def test_relevant_subset_returns_all_tables_when_small(target_db_path):
    connector = _connector_for(target_db_path)
    schema = SchemaIntrospector(connector.engine).introspect()
    subset = relevant_subset(schema, "how many customers are there", max_tables=12)
    assert set(subset) == {"customers", "orders"}
