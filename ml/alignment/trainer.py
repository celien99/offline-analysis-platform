from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .config import AlignmentConfig
from .dataset import AlignmentDataset
from .projector import AlignmentProjector


class InfoNCELoss(nn.Module):
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, anchor: torch.Tensor, positive: torch.Tensor) -> torch.Tensor:
        anchor = F.normalize(anchor, p=2, dim=1)
        positive = F.normalize(positive, p=2, dim=1)
        B = anchor.size(0)
        logits = anchor @ positive.T / self.temperature
        labels = torch.arange(B, device=anchor.device)
        loss_a = F.cross_entropy(logits, labels)
        loss_b = F.cross_entropy(logits.T, labels)
        return (loss_a + loss_b) / 2


class AlignmentTrainer:
    def __init__(self, config: AlignmentConfig | None = None, device: str = "cpu"):
        self.cfg = config or AlignmentConfig()
        self.device = torch.device(device)
        self.model = AlignmentProjector(self.cfg).to(self.device)
        self.model_name = "alignment_projector"

    def train(self, train_dataset: AlignmentDataset, val_dataset: AlignmentDataset,
              *, output_dir: str | None = None) -> dict[str, object]:
        cfg = self.cfg
        output_dir = Path(output_dir or cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_loader = DataLoader(train_dataset, batch_size=cfg.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=cfg.batch_size, shuffle=False)

        criterion = InfoNCELoss(temperature=cfg.temperature)
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=cfg.learning_rate)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg.epochs)

        best_val_loss = float("inf")
        patience_counter = 0
        history: list[dict] = []

        for epoch in range(cfg.epochs):
            self.model.train()
            train_loss = 0.0
            for ead_feats, dino_embs in train_loader:
                ead_feats = {k: v.to(self.device) for k, v in ead_feats.items()}
                dino_embs = dino_embs.to(self.device)
                optimizer.zero_grad()
                projected = self.model(
                    ead_feats["teacher"], ead_feats["student"],
                    ead_feats["difference"])
                loss = criterion(projected, dino_embs)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)
            scheduler.step()

            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for ead_feats, dino_embs in val_loader:
                    ead_feats = {k: v.to(self.device) for k, v in ead_feats.items()}
                    dino_embs = dino_embs.to(self.device)
                    projected = self.model(
                        ead_feats["teacher"], ead_feats["student"],
                        ead_feats["difference"])
                    val_loss += criterion(projected, dino_embs).item()

            val_loss /= len(val_loader)
            history.append({"epoch": epoch + 1, "train_loss": train_loss, "val_loss": val_loss})

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), output_dir / "best_projector.pt")
            else:
                patience_counter += 1

            if patience_counter >= cfg.early_stopping_patience:
                break

        return {"best_val_loss": best_val_loss, "history": history}

    def export_torchscript(self, output_path: str | Path) -> str:
        self.model.load_state_dict(torch.load(
            Path(self.cfg.output_dir) / "best_projector.pt", map_location=self.device))
        path = str(output_path)
        self.model.to_torchscript(path)
        return path
