from app.validators.sql_optimizer import SQLOptimizer
from app.validators.sql_validator import SQLValidator


def test_valid_select_passes():
    result = SQLValidator.validate("SELECT id, name FROM customers WHERE id = 1", engine_name="postgresql")
    assert result.is_valid


def test_drop_table_is_blocked():
    result = SQLValidator.validate("DROP TABLE customers", engine_name="postgresql")
    assert not result.is_valid
    assert result.error_code == "unsafe_sql"


def test_stacked_statements_are_blocked():
    result = SQLValidator.validate("SELECT * FROM customers; DROP TABLE customers;", engine_name="postgresql")
    assert not result.is_valid


def test_write_query_blocked_by_default():
    result = SQLValidator.validate("DELETE FROM customers WHERE id = 1", engine_name="postgresql", allow_write=False)
    assert not result.is_valid
    assert result.error_code == "unsafe_sql"


def test_write_query_allowed_when_opted_in():
    result = SQLValidator.validate("UPDATE customers SET name = 'x' WHERE id = 1", engine_name="postgresql", allow_write=True)
    assert result.is_valid


def test_garbled_sql_is_rejected():
    # sqlglot's parser is lenient and doesn't always raise on typos (it may
    # classify this as an unrecognized statement instead of a syntax error) -
    # what matters is that it's never treated as valid, runnable SQL.
    result = SQLValidator.validate("SELEC * FORM customers", engine_name="postgresql")
    assert not result.is_valid
    assert result.error_code in ("syntax_error", "parse_error", "unsafe_sql")


def test_admin_statements_always_blocked_even_with_write_allowed():
    result = SQLValidator.validate("GRANT ALL ON customers TO someuser", engine_name="postgresql", allow_write=True)
    assert not result.is_valid


def test_optimizer_flags_select_star_and_missing_limit():
    suggestions = SQLOptimizer.analyze("SELECT * FROM orders")
    messages = [s.message for s in suggestions]
    assert any("SELECT *" in m for m in messages)
    assert any("scan" in m.lower() for m in messages)


def test_optimizer_quiet_on_well_formed_query():
    suggestions = SQLOptimizer.analyze("SELECT id, name FROM customers WHERE country = 'US' LIMIT 10")
    # a targeted, limited query shouldn't trip the "full scan" warning
    assert not any("entire table" in s.message for s in suggestions)
