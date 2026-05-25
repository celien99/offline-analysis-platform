from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class DefectTreeNode(BaseModel):
    """缺陷分类树节点 — 支持多级层级结构"""

    __tablename__ = "defect_tree_nodes"

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("defect_tree_nodes.id"), nullable=True, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="0=root, 1=category, 2=subcategory, 3=leaf")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    defect_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
        comment="映射到 knowledge_entries.defect_type 的值"
    )
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # 自引用关系
    parent = relationship("DefectTreeNode", remote_side="DefectTreeNode.id", back_populates="children")
    children = relationship("DefectTreeNode", back_populates="parent", order_by="DefectTreeNode.level, DefectTreeNode.name")
