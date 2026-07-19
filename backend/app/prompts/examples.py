"""Few-shot examples shown to the SQL-generation model. Generic on purpose -
domain-specific examples are injected per-connection later via
prompt_builder if a deployment wants to add its own (see docs)."""
from __future__ import annotations

FEW_SHOT_EXAMPLES = [
    {
        "question": "How many customers do we have?",
        "sql": "SELECT COUNT(*) AS customer_count FROM customers;",
    },
    {
        "question": "Show total order amount by customer country",
        "sql": (
            "SELECT c.country, SUM(o.amount) AS total_amount\n"
            "FROM orders o JOIN customers c ON o.customer_id = c.id\n"
            "GROUP BY c.country\n"
            "ORDER BY total_amount DESC;"
        ),
    },
    {
        "question": "Top 5 customers by number of orders",
        "sql": (
            "SELECT c.name, COUNT(o.id) AS order_count\n"
            "FROM customers c JOIN orders o ON o.customer_id = c.id\n"
            "GROUP BY c.name\n"
            "ORDER BY order_count DESC\n"
            "LIMIT 5;"
        ),
    },
]
