from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


@pytest.mark.asyncio
async def test_list_clusters_empty() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/cluster/list")
        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_list_anomalies_empty() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/anomaly/list")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_knowledge_entries_empty() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/knowledge/entries")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_list_rules_empty() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/rules")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_list_models_empty() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/training/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data


@pytest.mark.asyncio
async def test_cluster_not_found() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/cluster/nonexistent12345")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_knowledge_search_no_results() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/knowledge/entries/search?q=zzz_nonexistent")
        assert response.status_code == 200
        assert response.json() == []
