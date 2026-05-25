from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import generate_uuid
from app.models.cluster import Cluster
from app.models.review import ReviewRecord
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
from app.repositories.review.repository import ReviewRepository

logger = get_logger(__name__)


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cluster_repo = ClusterRepository(session)
        self._membership_repo = ClusterMembershipRepository(session)
        self._review_repo = ReviewRepository(session)
        self._anomaly_repo = AnomalyRepository(session)

    async def submit_review(
        self,
        *,
        cluster_id: str,
        reviewer: str,
        action: str,
        defect_type: str | None = None,
        comment: str | None = None,
        new_cluster_name: str | None = None,
        merge_source_ids: list[str] | None = None,
        split_member_ids: list[str] | None = None,
    ) -> ReviewRecord:
        cluster = await self._cluster_repo.get_by_id(cluster_id)
        if cluster is None:
            raise NotFoundError("Cluster", cluster_id)

        previous_status = cluster.status

        match action:
            case "confirm_defect":
                await self._cluster_repo.update_review(
                    cluster_id,
                    review_status="real_defect",
                    defect_type=defect_type,
                    reviewed_by=reviewer,
                    name=new_cluster_name,
                )
                new_status = "reviewed"
            case "mark_false_alarm":
                await self._cluster_repo.update_review(
                    cluster_id,
                    review_status="false_alarm",
                    reviewed_by=reviewer,
                )
                new_status = "reviewed"
            case "rename":
                await self._cluster_repo.update_review(
                    cluster_id,
                    review_status=cluster.review_status or "real_defect",
                    reviewed_by=reviewer,
                    name=new_cluster_name,
                )
                new_status = "reviewed"
            case "split":
                new_status = await self._handle_split(
                    cluster, split_member_ids or [], reviewer
                )
            case "merge":
                new_status = await self._handle_merge(
                    cluster_id, merge_source_ids or [], reviewer
                )
            case "ignore":
                await self._cluster_repo.update_review(
                    cluster_id,
                    review_status="false_alarm",
                    reviewed_by=reviewer,
                )
                new_status = "reviewed"
            case _:
                new_status = previous_status

        # 审核完成后，将所有 member anomaly 标记为 reviewed，防止被重新聚类
        if new_status == "reviewed":
            member_ids = await self._membership_repo.get_anomaly_ids_by_cluster(cluster_id)
            for aid in member_ids:
                await self._anomaly_repo.update_status(aid, "reviewed")

        now = datetime.now(tz=timezone.utc)
        review = ReviewRecord(
            id=generate_uuid(),
            cluster_id=cluster_id,
            reviewer=reviewer,
            action=action,
            defect_type=defect_type,
            comment=comment,
            previous_status=previous_status,
            new_status=new_status,
            reviewed_at=now,
        )
        await self._review_repo.create(review)

        if action in ("confirm_defect", "mark_false_alarm"):
            knowledge_entry = await self._auto_generate_knowledge(
                cluster_id=cluster_id,
                review_action=action,
                defect_type=defect_type,
            )
            # 自动从 knowledge 生成 rules，闭合 Knowledge → Rules 链路
            if knowledge_entry is not None:
                from app.services.rule_engine import RuleEngineService
                rule_service = RuleEngineService(self._session)
                camera_ids_list: list[str] | None = None
                if knowledge_entry.camera_ids:
                    camera_ids_list = json.loads(knowledge_entry.camera_ids)
                await rule_service.auto_generate_rules_from_knowledge(
                    knowledge_entry_id=knowledge_entry.id,
                    camera_ids=camera_ids_list,
                )
                # 自动关联缺陷分类树节点
                if defect_type:
                    from app.services.taxonomy import TaxonomyService
                    taxonomy_service = TaxonomyService(self._session)
                    taxonomy_node_id = await taxonomy_service.auto_classify(defect_type)
                    if taxonomy_node_id:
                        await taxonomy_service.link_knowledge_to_taxonomy(
                            knowledge_entry.id, taxonomy_node_id
                        )

        logger.info(
            "review_submitted",
            cluster_id=cluster_id,
            action=action,
            reviewer=reviewer,
        )
        return review

    async def get_cluster_reviews(self, cluster_id: str) -> list[ReviewRecord]:
        return list(await self._review_repo.get_by_cluster(cluster_id))

    async def _handle_split(
        self,
        cluster: Cluster,
        split_member_ids: list[str],
        reviewer: str,
    ) -> str:
        if not split_member_ids:
            raise ValidationError(
                "split_member_ids is required for split action",
                code="MISSING_SPLIT_IDS",
            )

        current_member_ids = await self._membership_repo.get_anomaly_ids_by_cluster(
            cluster.id
        )
        valid_ids = [aid for aid in split_member_ids if aid in current_member_ids]
        if not valid_ids:
            raise ValidationError(
                "None of the provided split_member_ids belong to this cluster",
                code="INVALID_SPLIT_IDS",
            )

        new_cluster = Cluster(
            id=generate_uuid(),
            name=f"{cluster.name or 'cluster'}_split",
            sample_count=len(valid_ids),
            status="pending_review",
            hdbscan_label=-1,
            clustering_run_at=cluster.clustering_run_at,
        )
        await self._cluster_repo.create(new_cluster)

        moved_count = await self._membership_repo.move_memberships(
            source_cluster_id=cluster.id,
            target_cluster_id=new_cluster.id,
            anomaly_ids=valid_ids,
        )
        remaining_count = max(len(current_member_ids) - moved_count, 0)
        await self._cluster_repo.update_review(
            cluster.id,
            review_status=cluster.review_status or "real_defect",
            reviewed_by=reviewer,
        )

        await self._cluster_repo.update_fields(
            cluster.id, sample_count=remaining_count
        )

        logger.info(
            "cluster_split",
            original_cluster_id=cluster.id,
            new_cluster_id=new_cluster.id,
            moved_count=len(valid_ids),
        )
        return "reviewed"

    async def _handle_merge(
        self,
        target_cluster_id: str,
        merge_source_ids: list[str],
        reviewer: str,
    ) -> str:
        if not merge_source_ids:
            raise ValidationError(
                "merge_source_ids is required for merge action",
                code="MISSING_MERGE_IDS",
            )

        target = await self._cluster_repo.get_by_id(target_cluster_id)
        if target is None:
            raise NotFoundError("Cluster", target_cluster_id)

        total_sample_count = target.sample_count
        merged_representatives: list[str] = (
            json.loads(target.representative_ids) if target.representative_ids else []
        )

        for source_id in merge_source_ids:
            if source_id == target_cluster_id:
                continue
            source = await self._cluster_repo.get_by_id(source_id)
            if source is None:
                logger.warning("merge_source_not_found", source_id=source_id)
                continue

            source_member_ids = (
                await self._membership_repo.get_anomaly_ids_by_cluster(source_id)
            )
            moved_count = await self._membership_repo.move_memberships(
                source_cluster_id=source_id,
                target_cluster_id=target_cluster_id,
                anomaly_ids=source_member_ids,
            )

            total_sample_count += moved_count or source.sample_count
            if source.representative_ids:
                merged_representatives.extend(
                    json.loads(source.representative_ids)
                )

            await self._cluster_repo.soft_delete(source_id)

        await self._cluster_repo.update_fields(
            target_cluster_id,
            sample_count=total_sample_count,
            representative_ids=json.dumps(merged_representatives[:20]),
        )

        await self._cluster_repo.update_review(
            target_cluster_id,
            review_status=target.review_status or "real_defect",
            reviewed_by=reviewer,
        )

        logger.info(
            "cluster_merge",
            target_cluster_id=target_cluster_id,
            source_count=len(merge_source_ids),
            total_samples=total_sample_count,
        )
        return "reviewed"

    async def _auto_generate_knowledge(
        self,
        cluster_id: str,
        review_action: str,
        defect_type: str | None,
    ):
        """根据 review 结果自动创建 knowledge entry，并返回它以便联动生成 rules。"""
        from app.services.knowledge import KnowledgeService

        anomaly_ids = await self._membership_repo.get_anomaly_ids_by_cluster(cluster_id)
        anomalies = await self._anomaly_repo.get_by_ids(anomaly_ids)
        camera_ids = list({a.camera_id for a in anomalies}) if anomalies else None

        knowledge_service = KnowledgeService(self._session)
        return await knowledge_service.auto_generate_from_review(
            cluster_id=cluster_id,
            review_action=review_action,
            defect_type=defect_type,
            camera_ids=camera_ids,
        )
