from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str, label: str) -> None:
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid {label}: {name!r}")


async def find_similar_embeddings(
    session: AsyncSession,
    table_name: str,
    embedding_column: str,
    query_vector: list[float],
    *,
    top_k: int = 20,
    threshold: float = 0.7,
) -> list[dict[str, object]]:
    """Find similar embeddings using pgvector cosine distance."""
    _validate_identifier(table_name, "table_name")
    _validate_identifier(embedding_column, "embedding_column")
    stmt = text(f"""
        SELECT id,
               1 - ({embedding_column} <=> :query_vector) AS similarity
        FROM {table_name}
        WHERE 1 - ({embedding_column} <=> :query_vector) >= :threshold
        ORDER BY {embedding_column} <=> :query_vector
        LIMIT :top_k
    """)
    result = await session.execute(
        stmt,
        {
            "query_vector": query_vector,
            "threshold": threshold,
            "top_k": top_k,
        },
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]


async def vector_bulk_insert(
    session: AsyncSession,
    table_name: str,
    records: list[dict[str, object]],
) -> None:
    """Bulk insert records containing pgvector embeddings."""
    if not records:
        return
    _validate_identifier(table_name, "table_name")
    columns = list(records[0].keys())
    for col in columns:
        _validate_identifier(col, "column_name")
    placeholders = ", ".join(
        f"({', '.join(f':{col}_{i}' for col in columns)})"
        for i in range(len(records))
    )
    values: dict[str, object] = {}
    for i, record in enumerate(records):
        for col in columns:
            values[f"{col}_{i}"] = record[col]

    stmt = text(
        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES {placeholders}"
    )
    await session.execute(stmt, values)
