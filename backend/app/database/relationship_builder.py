"""
Builds a foreign-key relationship graph from a DatabaseSchema.

This is what lets the SQL-generation agent know that `orders.customer_id`
joins to `customers.id` without the LLM guessing, which is one of the
biggest accuracy levers in NL-to-SQL.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.database.introspector import DatabaseSchema


@dataclass
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str

    def as_join_hint(self) -> str:
        return f"{self.from_table}.{self.from_column} = {self.to_table}.{self.to_column}"


class RelationshipBuilder:
    @staticmethod
    def build(schema: DatabaseSchema) -> List[Relationship]:
        relationships: List[Relationship] = []
        for table in schema.tables:
            for fk in table.foreign_keys:
                relationships.append(
                    Relationship(
                        from_table=table.name,
                        from_column=fk.column,
                        to_table=fk.references_table,
                        to_column=fk.references_column,
                    )
                )
        return relationships

    @staticmethod
    def adjacency(relationships: List[Relationship]) -> Dict[str, List[Tuple[str, Relationship]]]:
        """table -> [(neighbor_table, relationship), ...] for shortest-join-path
        search when a question spans tables with no direct FK."""
        graph: Dict[str, List[Tuple[str, Relationship]]] = {}
        for rel in relationships:
            graph.setdefault(rel.from_table, []).append((rel.to_table, rel))
            graph.setdefault(rel.to_table, []).append((rel.from_table, rel))
        return graph

    @staticmethod
    def find_join_path(relationships: List[Relationship], start: str, end: str) -> List[Relationship]:
        """BFS shortest path of joins between two tables (helps the SQL
        generator bridge multi-hop questions like 'revenue by customer country'
        when country lives 2 joins away from the orders table)."""
        if start == end:
            return []
        graph = RelationshipBuilder.adjacency(relationships)
        from collections import deque

        visited = {start}
        queue = deque([(start, [])])
        while queue:
            node, path = queue.popleft()
            for neighbor, rel in graph.get(node, []):
                if neighbor in visited:
                    continue
                new_path = path + [rel]
                if neighbor == end:
                    return new_path
                visited.add(neighbor)
                queue.append((neighbor, new_path))
        return []
