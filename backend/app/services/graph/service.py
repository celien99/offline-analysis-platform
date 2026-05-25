from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.security import generate_uuid
from app.domain.graph.entities import GraphEdge, GraphNode, GraphQueryResult, Subgraph
from app.models.anomaly import AnomalyRecord
from app.models.graph import GraphBuildRecord, SimilarityEdge
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
from app.repositories.embedding.repository import EmbeddingRepository
from app.repositories.graph.repository import GraphBuildRecordRepository, GraphRepository

logger = get_logger(__name__)

DEFAULT_K = 10


class GraphService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._graph_repo = GraphRepository(session)
        self._build_record_repo = GraphBuildRecordRepository(session)

    # ── 图谱构建 ─────────────────────────────────────────

    async def build_graph(
        self, *, k: int = DEFAULT_K, seat_model_id: str | None = None,
    ) -> GraphBuildRecord:
        """构建/重建 KNN 相似度图谱"""
        record = GraphBuildRecord(
            id=generate_uuid(),
            status="running",
            k_neighbors=k,
            started_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        await self._build_record_repo.create(record)

        try:
            embedding_repo = EmbeddingRepository(self._session)

            # 获取所有未被审核的 embedding
            embedding_rows = await embedding_repo.get_embeddings_excluding_reviewed(
                seat_model_id=seat_model_id,
            )
            if not embedding_rows:
                record.status = "completed"
                record.total_anomalies = 0
                record.total_edges = 0
                record.completed_at = datetime.now(tz=timezone.utc).isoformat()
                await self._build_record_repo.update(record)
                logger.info("graph_build_empty")
                return record

            logger.info("graph_build_start", total_embeddings=len(embedding_rows))

            # 清空旧边
            await self._graph_repo.clear_all_edges()

            total_edges = 0
            batch: list[SimilarityEdge] = []
            batch_size = 500

            for anomaly_id, embedding_vec in embedding_rows:
                neighbors = await embedding_repo.find_similar(
                    query_vector=embedding_vec,
                    top_k=k + 1,  # +1 因为最近邻是自己
                    threshold=0.0,  # 不过滤，取所有结果
                )
                rank = 0
                for neighbor in neighbors:
                    neighbor_anomaly_id = str(neighbor["anomaly_id"])
                    if neighbor_anomaly_id == anomaly_id:
                        continue
                    rank += 1
                    if rank > k:
                        break
                    similarity = float(neighbor["similarity"])
                    edge = SimilarityEdge(
                        id=generate_uuid(),
                        source_anomaly_id=anomaly_id,
                        target_anomaly_id=neighbor_anomaly_id,
                        embedding_id=str(neighbor["embedding_id"]),
                        rank=rank,
                        similarity_score=round(similarity, 6),
                    )
                    batch.append(edge)

                    if len(batch) >= batch_size:
                        total_edges += await self._graph_repo.bulk_create_edges(batch)
                        batch = []

            # 剩余的
            if batch:
                total_edges += await self._graph_repo.bulk_create_edges(batch)

            record.status = "completed"
            record.total_anomalies = len(embedding_rows)
            record.total_edges = total_edges
            record.completed_at = datetime.now(tz=timezone.utc).isoformat()
            await self._build_record_repo.update(record)

            logger.info(
                "graph_build_complete",
                anomalies=len(embedding_rows),
                edges=total_edges,
            )
            return record

        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)[:512]
            await self._build_record_repo.update(record)
            logger.error("graph_build_failed", error=str(exc))
            raise

    # ── 查询 ─────────────────────────────────────────────

    async def get_neighbors(
        self, anomaly_id: str, *, k: int = DEFAULT_K
    ) -> GraphQueryResult:
        """获取指定异常的 K 近邻"""
        anomaly_repo = AnomalyRepository(self._session)
        cluster_membership_repo = ClusterMembershipRepository(self._session)
        cluster_repo = ClusterRepository(self._session)

        edges = await self._graph_repo.get_neighbors(anomaly_id, k=k)

        node_ids: set[str] = {anomaly_id}
        for e in edges:
            node_ids.add(e.target_anomaly_id)

        anomalies_map = await self._load_anomaly_nodes(
            anomaly_repo, list(node_ids),
            cluster_membership_repo, cluster_repo,
        )

        graph_edges = [
            GraphEdge(
                source_anomaly_id=e.source_anomaly_id,
                target_anomaly_id=e.target_anomaly_id,
                similarity_score=e.similarity_score,
                rank=e.rank,
            )
            for e in edges
        ]

        return GraphQueryResult(
            nodes=list(anomalies_map.values()),
            edges=graph_edges,
        )

    async def find_path(
        self, source_id: str, target_id: str, *, max_hops: int = 5
    ) -> GraphQueryResult:
        """BFS 查找两个异常之间的最短路径"""
        anomaly_repo = AnomalyRepository(self._session)
        cluster_membership_repo = ClusterMembershipRepository(self._session)
        cluster_repo = ClusterRepository(self._session)

        visited: set[str] = {source_id}
        parent: dict[str, str | None] = {source_id: None}
        queue = [source_id]
        found = False

        while queue and not found:
            current = queue.pop(0)
            if current == target_id:
                found = True
                break
            neighbors = await self._graph_repo.get_neighbors(current, k=DEFAULT_K)
            hop_count = self._count_hops(parent, current)
            if hop_count >= max_hops:
                continue
            for e in neighbors:
                if e.target_anomaly_id not in visited:
                    visited.add(e.target_anomaly_id)
                    parent[e.target_anomaly_id] = current
                    queue.append(e.target_anomaly_id)

        if not found:
            return GraphQueryResult()

        # 回溯路径
        path_ids: list[str] = []
        current: str | None = target_id
        while current is not None:
            path_ids.insert(0, current)
            current = parent.get(current)

        nodes_map = await self._load_anomaly_nodes(
            anomaly_repo, path_ids,
            cluster_membership_repo, cluster_repo,
        )

        path_nodes = [nodes_map[pid] for pid in path_ids if pid in nodes_map]
        path_edges: list[GraphEdge] = []
        for i in range(len(path_ids) - 1):
            edges = await self._graph_repo.get_neighbors(path_ids[i], k=DEFAULT_K)
            for e in edges:
                if e.target_anomaly_id == path_ids[i + 1]:
                    path_edges.append(GraphEdge(
                        source_anomaly_id=e.source_anomaly_id,
                        target_anomaly_id=e.target_anomaly_id,
                        similarity_score=e.similarity_score,
                        rank=e.rank,
                    ))
                    break

        return GraphQueryResult(nodes=path_nodes, edges=path_edges)

    async def get_subgraph(
        self, anomaly_id: str, *, k: int = DEFAULT_K
    ) -> Subgraph | None:
        """获取以指定异常为中心的子图"""
        anomaly_repo = AnomalyRepository(self._session)
        cluster_membership_repo = ClusterMembershipRepository(self._session)
        cluster_repo = ClusterRepository(self._session)

        center = await anomaly_repo.get_by_id(anomaly_id)
        if center is None:
            return None

        center_node = await self._build_graph_node(
            center, cluster_membership_repo, cluster_repo,
        )

        edges = await self._graph_repo.get_neighbors(anomaly_id, k=k)
        neighbor_ids = [e.target_anomaly_id for e in edges]
        neighbor_anomalies_map = await self._load_anomaly_nodes(
            anomaly_repo, neighbor_ids,
            cluster_membership_repo, cluster_repo,
        )

        neighbors = [
            (neighbor_anomalies_map[e.target_anomaly_id], e.similarity_score)
            for e in edges
            if e.target_anomaly_id in neighbor_anomalies_map
        ]

        graph_edges = [
            GraphEdge(
                source_anomaly_id=e.source_anomaly_id,
                target_anomaly_id=e.target_anomaly_id,
                similarity_score=e.similarity_score,
                rank=e.rank,
            )
            for e in edges
        ]

        return Subgraph(
            center_node=center_node,
            neighbors=neighbors,
            edges=graph_edges,
        )

    async def get_build_status(self) -> dict[str, Any]:
        """获取最近一次图谱构建状态"""
        record = await self._build_record_repo.get_latest_build()
        if record is None:
            return {"status": "never_built"}
        edge_count = await self._graph_repo.get_edge_count()
        return {
            "status": record.status,
            "total_anomalies": record.total_anomalies,
            "total_edges": record.total_edges,
            "current_edge_count": edge_count,
            "k_neighbors": record.k_neighbors,
            "error_message": record.error_message,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
        }

    # ── 内部辅助 ─────────────────────────────────────────

    async def _load_anomaly_nodes(
        self,
        anomaly_repo: AnomalyRepository,
        anomaly_ids: list[str],
        membership_repo: ClusterMembershipRepository,
        cluster_repo: ClusterRepository,
    ) -> dict[str, GraphNode]:
        """批量加载异常节点信息"""
        result: dict[str, GraphNode] = {}
        for aid in anomaly_ids:
            anomaly = await anomaly_repo.get_by_id(aid)
            if anomaly is None:
                continue
            node = await self._build_graph_node(anomaly, membership_repo, cluster_repo)
            result[aid] = node
        return result

    async def _build_graph_node(
        self,
        anomaly: AnomalyRecord,
        membership_repo: ClusterMembershipRepository,
        cluster_repo: ClusterRepository,
    ) -> GraphNode:
        cluster_ids = await membership_repo.get_cluster_ids_by_anomaly(anomaly.id)
        cluster_id = cluster_ids[0] if cluster_ids else None
        cluster_name = None
        defect_type = None
        umap_x = None
        umap_y = None

        if cluster_id:
            cluster = await cluster_repo.get_by_id(cluster_id)
            if cluster:
                cluster_name = cluster.name
                defect_type = cluster.defect_type
                umap_x = cluster.umap_x
                umap_y = cluster.umap_y

        return GraphNode(
            anomaly_id=anomaly.id,
            camera_id=anomaly.camera_id,
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            defect_type=defect_type,
            umap_x=umap_x,
            umap_y=umap_y,
        )

    @staticmethod
    def _count_hops(parent: dict[str, str | None], node_id: str) -> int:
        count = 0
        current: str | None = node_id
        while current is not None:
            current = parent.get(current)
            if current is not None:
                count += 1
        return count
