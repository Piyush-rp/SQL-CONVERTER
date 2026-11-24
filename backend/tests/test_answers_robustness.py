"""Binary/unusual values in results, schema (structure) questions answered
without the LLM, and retrying when the model replies without SQL."""
import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from app.agents.execution_agent import _json_safe
from app.agents.validator_agent import ValidatorAgent
from app.database.introspector import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from app.llm.response_parser import ResponseParser
from app.workflows.schema_questions import answer_structure_question, is_structure_question


def test_binary_and_special_values_become_json_safe():
    row = [b"\x1f\x8b\x08\x00" + bytes(3000), b"plain text", Decimal("12.50"), date(2026, 1, 2),
           datetime(2026, 1, 2, 3, 4, 5), uuid.UUID(int=1), "x" * 5000, None, 7]
    safe = [_json_safe(v) for v in row]
    json.dumps(safe)  # must not raise
    assert safe[0] == "<binary, 2.9 KB>"
    assert safe[1] == "plain text"
    assert safe[2] == 12.5
    assert safe[3] == "2026-01-02"
    assert safe[6].endswith("(5000 characters)") and len(safe[6]) < 2100
    assert safe[7] is None and safe[8] == 7


def _schema():
    family = TableInfo(name="family", schema=None, primary_key=["rfam_acc"], columns=[
        ColumnInfo("rfam_acc", "VARCHAR", False, None, True), ColumnInfo("description", "VARCHAR", True, None, False)])
    family_file = TableInfo(name="_family_file", schema=None, columns=[
        ColumnInfo("rfam_acc", "VARCHAR", False, None, False), ColumnInfo("seed", "LONGBLOB", False, None, False)],
        foreign_keys=[ForeignKeyInfo("rfam_acc", "family", "rfam_acc")])
    return DatabaseSchema(engine_name="mysql", database_name="Rfam", tables=[family_file, family])


def test_structure_questions_are_detected_but_data_questions_are_not():
    for q in ["give me the schema", "give me the schema of the database", "list all tables",
              "what tables are there?", "give me the details odf the family file table",
              "describe the family table", "columns of family"]:
        assert is_structure_question(q), q
    for q in ["which 5 families have the most full region entries?", "show 3 rows from the family table",
              "total revenue by month", "how many rows are in each table?"]:
        assert not is_structure_question(q), q


def test_whole_schema_answer_lists_tables():
    answer = answer_structure_question("give me the schema", _schema())
    assert answer["execution"]["columns"] == ["table", "columns", "primary key", "links to"]
    assert [r[0] for r in answer["execution"]["rows"]] == ["_family_file", "family"]
    assert "2 tables" in answer["explanation"]


def test_specific_table_answer_prefers_the_most_specific_name():
    answer = answer_structure_question("give me the details of the family file table", _schema())
    assert answer["execution"]["columns"] == ["column", "type", "nullable", "primary key", "references"]
    assert [r[0] for r in answer["execution"]["rows"]] == ["rfam_acc", "seed"]
    assert answer["execution"]["rows"][0][4] == "family.rfam_acc"
    assert "`_family_file` has 2 columns" in answer["explanation"]


def test_reply_without_sql_is_retried_not_abandoned():
    parsed = ResponseParser.parse("Sure! Here is some information about the schema.")
    assert parsed.sql is None and parsed.cannot_answer_reason is None

    state = ValidatorAgent().run({"sql": None, "engine_name": "sqlite"})
    assert state["validation"].is_valid is False
    assert "```sql" in state["last_error"]
