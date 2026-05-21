from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
    columns = list(records[0].keys())
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
