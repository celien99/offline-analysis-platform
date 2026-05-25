"""度量学习训练模块 — ArcFace / Triplet Loss 缺陷嵌入学习"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision import models


class ArcFaceLoss(nn.Module):
    """ArcFace: Additive Angular Margin Loss

    在特征向量和分类权重之间加入角度边际，迫使同类嵌入更紧凑。
    """

    def __init__(
        self,
        embedding_size: int,
        num_classes: int,
        scale: float = 30.0,
        margin: float = 0.5,
    ) -> None:
        super().__init__()
        self._scale = scale
        self._margin = margin
        self._weight = nn.Parameter(torch.FloatTensor(num_classes, embedding_size))
        nn.init.xavier_uniform_(self._weight)

    def forward(
        self, embeddings: torch.Tensor, labels: torch.Tensor
    ) -> torch.Tensor:
        # 归一化 embedding 和 weight
        normalized_embeddings = F.normalize(embeddings)
        normalized_weight = F.normalize(self._weight)
        cosine = F.linear(normalized_embeddings, normalized_weight)

        # ArcFace 角度边际
        theta = torch.acos(torch.clamp(cosine, -1.0 + 1e-7, 1.0 - 1e-7))
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1)
        theta_with_margin = theta + one_hot * self._margin
        cosine_with_margin = torch.cos(theta_with_margin)

        output = self._scale * cosine_with_margin
        return F.cross_entropy(output, labels)


class TripletLoss(nn.Module):
    """Triplet Loss — 同类嵌入距离小于异类嵌入距离"""

    def __init__(self, margin: float = 1.0) -> None:
        super().__init__()
        self._margin = margin

    def forward(
        self,
        anchor: torch.Tensor,
        positive: torch.Tensor,
        negative: torch.Tensor,
    ) -> torch.Tensor:
        pos_dist = F.pairwise_distance(anchor, positive, p=2)
        neg_dist = F.pairwise_distance(anchor, negative, p=2)
        loss = F.relu(pos_dist - neg_dist + self._margin)
        return loss.mean()


class EmbeddingBackbone(nn.Module):
    """从分类网络提取 embedding 的骨干网络"""

    def __init__(
        self,
        backbone_type: str = "mobilenet_v3_small",
        embedding_size: int = 256,
        pretrained: bool = True,
    ) -> None:
        super().__init__()
        self._backbone_type = backbone_type
        self._embedding_size = embedding_size

        match backbone_type:
            case "mobilenet_v3_small":
                backbone = models.mobilenet_v3_small(
                    weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
                    if pretrained else None
                )
                in_features = backbone.classifier[-1].in_features
                backbone.classifier = nn.Identity()
            case "resnet18":
                backbone = models.resnet18(
                    weights=models.ResNet18_Weights.IMAGENET1K_V1
                    if pretrained else None
                )
                in_features = backbone.fc.in_features
                backbone.fc = nn.Identity()
            case "efficientnet_b0":
                backbone = models.efficientnet_b0(
                    weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1
                    if pretrained else None
                )
                in_features = backbone.classifier[-1].in_features
                backbone.classifier = nn.Identity()
            case _:
                raise ValueError(f"Unknown backbone: {backbone_type}")

        self._backbone = backbone
        self._embedding = nn.Sequential(
            nn.Linear(in_features, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, embedding_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self._backbone(x)
        return F.normalize(self._embedding(features))

    @property
    def embedding_size(self) -> int:
        return self._embedding_size

    @property
    def backbone_type(self) -> str:
        return self._backbone_type


class MetricEmbeddingTrainer:
    """度量学习训练器 — 使用 ArcFace 或 Triplet Loss 训练缺陷嵌入模型"""

    def __init__(
        self,
        backbone_type: str = "mobilenet_v3_small",
        embedding_size: int = 256,
        image_size: tuple[int, int] = (224, 224),
        device: str = "cpu",
        learning_rate: float = 0.001,
        loss_type: str = "arcface",  # arcface / triplet
        arcface_scale: float = 30.0,
        arcface_margin: float = 0.5,
        triplet_margin: float = 1.0,
    ) -> None:
        self._backbone_type = backbone_type
        self._embedding_size = embedding_size
        self._image_size = image_size
        self._device = device
        self._learning_rate = learning_rate
        self._loss_type = loss_type

        self._model = EmbeddingBackbone(
            backbone_type=backbone_type,
            embedding_size=embedding_size,
        ).to(device)

        self._arcface_scale = arcface_scale
        self._arcface_margin = arcface_margin
        self._triplet_margin = triplet_margin

    @property
    def model(self) -> EmbeddingBackbone:
        return self._model

    def train_with_arcface(
        self,
        train_dataset: Dataset,
        val_dataset: Dataset,
        *,
        num_classes: int,
        batch_size: int = 32,
        epochs: int = 50,
        early_stopping_patience: int = 10,
        output_dir: str | Path = "./models",
    ) -> dict[str, Any]:
        """使用 ArcFace Loss 训练"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

        arcface = ArcFaceLoss(
            embedding_size=self._embedding_size,
            num_classes=num_classes,
            scale=self._arcface_scale,
            margin=self._arcface_margin,
        ).to(self._device)

        optimizer = torch.optim.Adam(
            list(self._model.parameters()) + list(arcface.parameters()),
            lr=self._learning_rate,
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", patience=5, factor=0.5,
        )

        best_val_loss = float("inf")
        patience_counter = 0
        history: dict[str, list[float]] = {"train_loss": [], "val_loss": [], "val_accuracy": []}

        for epoch in range(epochs):
            self._model.train()
            train_loss = 0.0
            for inputs, targets in train_loader:
                inputs = inputs.to(self._device)
                targets = targets.to(self._device)

                optimizer.zero_grad()
                embeddings = self._model(inputs)
                loss = arcface(embeddings, targets)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            avg_train_loss = train_loss / len(train_loader)

            # 验证 — 使用 embedding 相似度匹配来评估
            self._model.eval()
            val_loss = 0.0
            correct = 0
            total = 0
            with torch.no_grad():
                for inputs, targets in val_loader:
                    inputs = inputs.to(self._device)
                    targets = targets.to(self._device)
                    embeddings = self._model(inputs)
                    loss = arcface(embeddings, targets)
                    val_loss += loss.item()

                    # 用 ArcFace weight 做分类评估
                    normalized_emb = F.normalize(embeddings)
                    normalized_w = F.normalize(arcface._weight)
                    logits = F.linear(normalized_emb, normalized_w)
                    _, predicted = logits.max(1)
                    total += targets.size(0)
                    correct += predicted.eq(targets).sum().item()

            avg_val_loss = val_loss / len(val_loader)
            val_accuracy = correct / total if total > 0 else 0.0

            history["train_loss"].append(avg_train_loss)
            history["val_loss"].append(avg_val_loss)
            history["val_accuracy"].append(val_accuracy)

            scheduler.step(avg_val_loss)

            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                torch.save(
                    {
                        "model_state_dict": self._model.state_dict(),
                        "arcface_state_dict": arcface.state_dict(),
                        "backbone_type": self._backbone_type,
                        "embedding_size": self._embedding_size,
                    },
                    output_dir / "best_metric_model.pt",
                )
            else:
                patience_counter += 1

            if patience_counter >= early_stopping_patience:
                break

        # 导出仅含 embedding backbone 的 TorchScript
        self._model.eval()
        example = torch.randn(1, 3, *self._image_size).to(self._device)
        traced = torch.jit.trace(self._model, example)
        traced.save(str(output_dir / "metric_embedding.pt"))

        return {
            "best_val_loss": best_val_loss,
            "best_val_accuracy": max(history["val_accuracy"]),
            "final_epoch": epoch + 1,
            "history": history,
            "embedding_size": self._embedding_size,
            "backbone_type": self._backbone_type,
        }

    def train_with_triplet(
        self,
        triplets: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
        *,
        batch_size: int = 32,
        epochs: int = 30,
        output_dir: str | Path = "./models",
    ) -> dict[str, Any]:
        """使用 Triplet Loss 训练（锚点，正样本，负样本）"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        class _TripletDataset(Dataset):
            def __init__(self, triplets: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]):
                self._triplets = triplets

            def __len__(self) -> int:
                return len(self._triplets)

            def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
                return self._triplets[idx]

        ds = _TripletDataset(triplets)
        loader = DataLoader(ds, batch_size=batch_size, shuffle=True, num_workers=0)

        triplet_loss = TripletLoss(margin=self._triplet_margin).to(self._device)
        optimizer = torch.optim.Adam(self._model.parameters(), lr=self._learning_rate)

        best_loss = float("inf")
        history: dict[str, list[float]] = {"train_loss": []}

        for epoch in range(epochs):
            self._model.train()
            epoch_loss = 0.0
            for anchor, positive, negative in loader:
                anchor = anchor.to(self._device)
                positive = positive.to(self._device)
                negative = negative.to(self._device)

                optimizer.zero_grad()
                anchor_emb = self._model(anchor)
                pos_emb = self._model(positive)
                neg_emb = self._model(negative)
                loss = triplet_loss(anchor_emb, pos_emb, neg_emb)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)
            history["train_loss"].append(avg_loss)

            if avg_loss < best_loss:
                best_loss = avg_loss
                torch.save(
                    self._model.state_dict(),
                    output_dir / "best_triplet_model.pt",
                )

        # 导出 TorchScript
        self._model.eval()
        example = torch.randn(1, 3, *self._image_size).to(self._device)
        traced = torch.jit.trace(self._model, example)
        traced.save(str(output_dir / "metric_embedding.pt"))

        return {
            "best_loss": best_loss,
            "final_epoch": epochs,
            "history": history,
            "embedding_size": self._embedding_size,
            "backbone_type": self._backbone_type,
        }

    def load_checkpoint(self, checkpoint_path: str | Path) -> None:
        ckpt = torch.load(str(checkpoint_path), map_location=self._device)
        if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
            self._model.load_state_dict(ckpt["model_state_dict"])
        else:
            self._model.load_state_dict(ckpt)
        self._model.eval()

    def export_torchscript(self, output_path: str | Path) -> str:
        output_path = Path(output_path)
        self._model.eval()
        example = torch.randn(1, 3, *self._image_size).to(self._device)
        traced = torch.jit.trace(self._model, example)
        traced.save(str(output_path))
        return str(output_path)
