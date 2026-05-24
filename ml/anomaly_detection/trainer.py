"""FastFlow 训练器。

在正常图像上训练，学习正常特征的分布。
复用 FilterClassifierTrainer 的 train/export 模式。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T

from .fastflow import FastFlowConfig, FastFlowModel


class _ImageFolderDataset(Dataset):
    """从图像文件路径列表加载数据。"""

    def __init__(self, image_paths: list[str], transform, image_size: tuple[int, int]) -> None:
        self._paths = image_paths
        self._transform = transform
        self._resize = T.Resize(image_size)

    def __len__(self) -> int:
        return len(self._paths)

    def __getitem__(self, idx: int) -> torch.Tensor:
        img = Image.open(self._paths[idx]).convert("RGB")
        img = self._resize(img)
        return self._transform(img)


class FastFlowTrainer:
    """在正常图像上训练 FastFlow 模型。

    训练目标：最大化 latent z 在标准正态分布下的似然。
    等价于最小化 NLL = 0.5 * z^2 的均值。
    """

    def __init__(
        self,
        config: FastFlowConfig | None = None,
        device: str = "cpu",
        learning_rate: float = 1e-3,
    ) -> None:
        self._config = config or FastFlowConfig()
        self._device = device
        self._lr = learning_rate
        self._model = FastFlowModel(self._config).to(device)
        self._transform = T.Compose([
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    @property
    def model(self) -> FastFlowModel:
        return self._model

    @property
    def config(self) -> FastFlowConfig:
        return self._config

    def train(
        self,
        image_paths: list[str],
        *,
        batch_size: int = 8,
        epochs: int = 50,
        validation_split: float = 0.1,
        output_dir: str | Path = "./models/fastflow",
        freeze_backbone: bool = True,
    ) -> dict[str, object]:
        """在正常图像上训练 FastFlow 模型。

        Args:
            image_paths: 正常（无缺陷）图像文件路径列表
            batch_size: 批大小
            epochs: 最大训练轮数
            validation_split: 验证集比例
            output_dir: 模型输出目录
            freeze_backbone: 是否冻结 backbone（推荐 True）

        Returns:
            dict with: best_val_loss, final_epoch, history
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if len(image_paths) < 4:
            return {"status": "failed", "error": f"Need >= 4 images, got {len(image_paths)}"}

        # 数据集划分
        n_val = max(1, int(len(image_paths) * validation_split))
        n_train = len(image_paths) - n_val
        indices = np.random.RandomState(42).permutation(len(image_paths))
        train_paths = [image_paths[i] for i in indices[:n_train]]
        val_paths = [image_paths[i] for i in indices[n_train:]]

        train_ds = _ImageFolderDataset(train_paths, self._transform, self._config.input_size)
        val_ds = _ImageFolderDataset(val_paths, self._transform, self._config.input_size)

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

        if freeze_backbone:
            self._model.freeze_backbone()

        optimizer = torch.optim.Adam([
            p for p in self._model.parameters() if p.requires_grad
        ], lr=self._lr, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)

        best_val_loss = float("inf")
        patience_counter = 0
        history: dict[str, list[float]] = {"train_loss": [], "val_loss": []}

        for epoch in range(epochs):
            # Training
            self._model.train()
            train_loss = 0.0
            for batch in train_loader:
                batch = batch.to(self._device)
                optimizer.zero_grad()
                latents = self._model(batch)
                # 优化目标：z 接近 N(0,1) → 最小化 z^2 的均值
                loss = sum((z ** 2).mean() for z in latents) / len(latents)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            avg_train_loss = train_loss / len(train_loader)
            scheduler.step()

            # Validation
            self._model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch in val_loader:
                    batch = batch.to(self._device)
                    latents = self._model(batch)
                    loss = sum((z ** 2).mean() for z in latents) / len(latents)
                    val_loss += loss.item()

            avg_val_loss = val_loss / len(val_loader)
            history["train_loss"].append(avg_train_loss)
            history["val_loss"].append(avg_val_loss)

            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                torch.save(self._model.state_dict(), output_dir / "best_model.pt")
            else:
                patience_counter += 1

            if patience_counter >= 15:
                break

        # 加载最佳模型
        best_path = output_dir / "best_model.pt"
        if best_path.exists():
            self._model.load_state_dict(torch.load(best_path, map_location=self._device))

        return {
            "best_val_loss": best_val_loss,
            "final_epoch": epoch + 1,
            "history": history,
        }

    def export_torchscript(self, output_path: str | Path) -> str:
        """将模型导出为 TorchScript (需要推理用 predict 方法)。

        由于 predict 方法使用了 @torch.no_grad() 装饰器且包含复杂逻辑，
        我们改为导出 forward 方法并包装推理逻辑在外部。
        """
        output_path = Path(output_path)
        self._model.eval()

        # 使用 forward (返回 latents) → 推理侧自行算 NLL
        example = torch.randn(1, 3, *self._config.input_size).to(self._device)
        traced = torch.jit.trace(self._model, example)
        traced.save(str(output_path))
        return str(output_path)

    def load_checkpoint(self, checkpoint_path: str | Path) -> None:
        """从检查点加载模型权重。"""
        checkpoint = torch.load(str(checkpoint_path), map_location=self._device)
        if isinstance(checkpoint, dict):
            self._model.load_state_dict(checkpoint)
        self._model.eval()
