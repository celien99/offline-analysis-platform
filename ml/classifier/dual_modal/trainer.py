from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .config import DualModalConfig
from .dataset import DualModalDataset
from .model import DualModalFilter


class FocalLoss(nn.Module):
    """Focal loss for imbalanced binary classification."""

    def __init__(self, gamma: float = 2.0, alpha: float = 0.75):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce_loss)
        alpha_t = torch.where(targets == 1, self.alpha, 1 - self.alpha)
        return (alpha_t * (1 - pt) ** self.gamma * ce_loss).mean()


class DualModalTrainer:
    """Trainer for DualModalFilter with dual-branch learning rates and early stopping."""

    def __init__(self, config: DualModalConfig | None = None, device: str = "cpu"):
        self.config = config or DualModalConfig()
        self.device = torch.device(device)
        self.model = DualModalFilter(
            num_classes=self.config.num_classes,
            image_size=self.config.image_size,
            feature_dropout_rate=self.config.feature_dropout_rate,
        ).to(self.device)
        self.model_name = "dual_modal_filter"

    def train(
        self,
        train_dataset: DualModalDataset,
        val_dataset: DualModalDataset,
        *,
        output_dir: str | None = None,
    ) -> dict[str, object]:
        """Run full training loop with early stopping and LR scheduling."""
        config = self.config
        output_dir = Path(output_dir or config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_loader = DataLoader(
            train_dataset, batch_size=config.batch_size, shuffle=True
        )
        val_loader = DataLoader(
            val_dataset, batch_size=config.batch_size, shuffle=False
        )

        criterion = FocalLoss(gamma=config.focal_gamma, alpha=config.focal_alpha)
        optimizer = torch.optim.Adam([
            {"params": self.model.image_backbone.parameters(),
             "lr": config.image_branch_lr},
            {"params": self.model.image_proj.parameters(),
             "lr": config.learning_rate},
            {"params": self.model.ead_projector.parameters(),
             "lr": config.learning_rate},
            {"params": self.model.ead_proj.parameters(),
             "lr": config.learning_rate},
            {"params": self.model.fusion.parameters(),
             "lr": config.learning_rate},
        ])
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=5
        )

        best_val_loss = float("inf")
        best_epoch = 0
        patience_counter = 0
        history: list[dict] = []

        for epoch in range(config.epochs):
            # --- Training ---
            self.model.train()
            train_loss = 0.0
            for imgs, features, labels in train_loader:
                imgs = imgs.to(self.device)
                labels = labels.to(self.device)
                if features is not None:
                    features = {k: v.to(self.device) for k, v in features.items()}

                optimizer.zero_grad()
                logits = self.model(imgs, features)
                loss = criterion(logits, labels)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)

            # --- Validation ---
            self.model.eval()
            val_loss = 0.0
            correct = 0
            total = 0
            with torch.no_grad():
                for imgs, features, labels in val_loader:
                    imgs = imgs.to(self.device)
                    labels = labels.to(self.device)
                    if features is not None:
                        features = {k: v.to(self.device)
                                    for k, v in features.items()}
                    logits = self.model(imgs, features)
                    val_loss += criterion(logits, labels).item()
                    preds = logits.argmax(dim=1)
                    correct += (preds == labels).sum().item()
                    total += labels.size(0)

            val_loss /= len(val_loader)
            val_acc = correct / total if total > 0 else 0.0
            scheduler.step(val_loss)

            history.append({
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "val_acc": val_acc,
            })

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch + 1
                patience_counter = 0
                torch.save(
                    self.model.state_dict(), output_dir / "best_model.pt"
                )
            else:
                patience_counter += 1

            if patience_counter >= config.early_stopping_patience:
                break

        # Restore best model
        self.model.load_state_dict(
            torch.load(output_dir / "best_model.pt")
        )
        return {
            "best_val_loss": best_val_loss,
            "best_val_acc": val_acc,
            "best_epoch": best_epoch,
            "history": history,
            "early_stopped": patience_counter >= config.early_stopping_patience,
        }

    def export_torchscript(self, output_path: str | Path) -> str:
        """Export model to TorchScript for online inference."""
        path = str(output_path)
        self.model.to_torchscript(path)
        return path

    def save_checkpoint(self, output_path: str | Path,
                        metrics: dict | None = None) -> str:
        """Save full training checkpoint."""
        path = str(output_path)
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "config": self.config,
            "metrics": metrics or {},
        }
        torch.save(checkpoint, path)
        return path

    def load_checkpoint(self, checkpoint_path: str | Path) -> None:
        """Load model weights from a checkpoint."""
        checkpoint = torch.load(str(checkpoint_path), map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
