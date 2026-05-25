from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms


class FilterClassifierTrainer:
    """Lightweight filter classifier trainer for false alarm suppression.

    Trains a MobileNetV3/EfficientNet/ResNet18 binary classifier
    to distinguish real defects from false alarms.
    """

    def __init__(
        self,
        model_type: str = "mobilenet_v3_small",
        num_classes: int = 2,
        image_size: tuple[int, int] = (224, 224),
        device: str = "cpu",
        learning_rate: float = 0.001,
    ) -> None:
        self._model_type = model_type
        self._num_classes = num_classes
        self._image_size = image_size
        self._device = device
        self._learning_rate = learning_rate

        self._model = self._build_model()
        self._transform = self._build_transform()

    def _build_model(self) -> nn.Module:
        match self._model_type:
            case "mobilenet_v3_small":
                model = models.mobilenet_v3_small(
                    weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
                )
                in_features = model.classifier[-1].in_features
                model.classifier[-1] = nn.Linear(in_features, self._num_classes)
            case "efficientnet_b0":
                model = models.efficientnet_b0(
                    weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1
                )
                in_features = model.classifier[-1].in_features
                model.classifier[-1] = nn.Linear(in_features, self._num_classes)
            case "resnet18":
                model = models.resnet18(
                    weights=models.ResNet18_Weights.IMAGENET1K_V1
                )
                in_features = model.fc.in_features
                model.fc = nn.Linear(in_features, self._num_classes)
            case _:
                raise ValueError(f"Unknown model type: {self._model_type}")

        return model.to(self._device)

    def _build_transform(self) -> transforms.Compose:
        return transforms.Compose([
            transforms.Resize(self._image_size),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    @property
    def model_name(self) -> str:
        return self._model_type

    @property
    def num_classes(self) -> int:
        return self._num_classes

    def train(
        self,
        train_dataset: Dataset,
        val_dataset: Dataset,
        *,
        batch_size: int = 32,
        epochs: int = 50,
        class_names: list[str] | None = None,
        early_stopping_patience: int = 10,
        output_dir: str | Path = "./models",
    ) -> dict[str, object]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_loader = DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True, num_workers=0
        )
        val_loader = DataLoader(
            val_dataset, batch_size=batch_size, shuffle=False, num_workers=0
        )

        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(
            self._model.parameters(), lr=self._learning_rate
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", patience=5, factor=0.5
        )

        best_val_loss = float("inf")
        patience_counter = 0
        history: dict[str, list[float]] = {
            "train_loss": [],
            "val_loss": [],
            "val_accuracy": [],
        }

        for epoch in range(epochs):
            self._model.train()
            train_loss = 0.0
            for inputs, targets in train_loader:
                inputs = inputs.to(self._device)
                targets = targets.to(self._device)

                optimizer.zero_grad()
                outputs = self._model(inputs)
                loss = criterion(outputs, targets)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            avg_train_loss = train_loss / len(train_loader)

            self._model.eval()
            val_loss = 0.0
            correct = 0
            total = 0
            with torch.no_grad():
                for inputs, targets in val_loader:
                    inputs = inputs.to(self._device)
                    targets = targets.to(self._device)
                    outputs = self._model(inputs)
                    loss = criterion(outputs, targets)
                    val_loss += loss.item()
                    _, predicted = outputs.max(1)
                    total += targets.size(0)
                    correct += predicted.eq(targets).sum().item()

            avg_val_loss = val_loss / len(val_loader)
            val_accuracy = correct / total

            history["train_loss"].append(avg_train_loss)
            history["val_loss"].append(avg_val_loss)
            history["val_accuracy"].append(val_accuracy)

            scheduler.step(avg_val_loss)

            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                torch.save(
                    self._model.state_dict(),
                    output_dir / "best_model.pt",
                )
            else:
                patience_counter += 1

            if patience_counter >= early_stopping_patience:
                break

        return {
            "best_val_loss": best_val_loss,
            "best_val_accuracy": max(history["val_accuracy"]),
            "final_epoch": epoch + 1,
            "history": history,
        }

    def load_checkpoint(self, checkpoint_path: str | Path) -> None:
        """Load model weights from a checkpoint file."""
        checkpoint = torch.load(str(checkpoint_path), map_location=self._device)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            self._model.load_state_dict(checkpoint["model_state_dict"])
        else:
            self._model.load_state_dict(checkpoint)
        self._model.eval()

    def fine_tune(
        self,
        checkpoint_path: str | Path,
        train_dataset: Dataset,
        val_dataset: Dataset,
        *,
        batch_size: int = 32,
        epochs: int = 20,
        class_names: list[str] | None = None,
        early_stopping_patience: int = 5,
        output_dir: str | Path = "./models",
    ) -> dict[str, object]:
        """从已有 checkpoint 微调模型，仅在新数据上训练。

        相比完整训练使用更少的 epoch、更低的 LR 和更激进的早停，
        适合在少量新增标签上的增量学习。
        """
        self.load_checkpoint(checkpoint_path)
        # 增量训练使用原始 LR 的 1/5，避免灾难性遗忘
        original_lr = self._learning_rate
        self._learning_rate = original_lr / 5.0
        try:
            return self.train(
                train_dataset=train_dataset,
                val_dataset=val_dataset,
                batch_size=batch_size,
                epochs=epochs,
                class_names=class_names,
                early_stopping_patience=early_stopping_patience,
                output_dir=output_dir,
            )
        finally:
            self._learning_rate = original_lr

    def save_checkpoint(
        self, output_path: str | Path, metrics: dict | None = None
    ) -> str:
        """保存完整 checkpoint（state_dict + 元数据），供后续增量训练复用。"""
        output_path = Path(output_path)
        torch.save(
            {
                "model_state_dict": self._model.state_dict(),
                "model_type": self._model_type,
                "num_classes": self._num_classes,
                "metrics": metrics or {},
            },
            output_path,
        )
        return str(output_path)

    def export_torchscript(self, output_path: str | Path) -> str:
        output_path = Path(output_path)
        self._model.eval()
        example = torch.randn(1, 3, *self._image_size).to(self._device)
        traced = torch.jit.trace(self._model, example)
        traced.save(str(output_path))
        return str(output_path)

    def export_onnx(self, output_path: str | Path) -> str:
        output_path = Path(output_path)
        self._model.eval()
        example = torch.randn(1, 3, *self._image_size).to(self._device)
        torch.onnx.export(
            self._model,
            example,
            str(output_path),
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={
                "input": {0: "batch_size"},
                "output": {0: "batch_size"},
            },
        )
        return str(output_path)
