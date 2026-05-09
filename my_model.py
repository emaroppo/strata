from pathlib import Path

import timm
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from auto_labeller.model import BaseModel, Prediction


class _ImageDataset(Dataset):
    def __init__(self, samples: list[dict], classes: list[str], transform):
        self.samples = samples
        self.class_to_idx = {c: i for i, c in enumerate(classes)}
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        sample = self.samples[idx]
        image = Image.open(sample["path"]).convert("RGB")
        image = self.transform(image)
        label_vec = torch.zeros(len(self.class_to_idx))
        for lbl in sample["labels"]:
            if lbl in self.class_to_idx:
                label_vec[self.class_to_idx[lbl]] = 1.0
        return image, label_vec


class MyModel(BaseModel):
    """ConvNeXt V2 Base fine-tuned multi-label classifier.

    Uses timm's ``convnextv2_base`` with ImageNet-22k pre-trained weights.
    Supports multi-label outputs via ``BCEWithLogitsLoss``.
    """

    IMG_SIZE = 224
    MEAN = (0.485, 0.456, 0.406)
    STD = (0.229, 0.224, 0.225)

    def __init__(
        self,
        num_epochs: int = 2,
        batch_size: int = 32,
        lr: float = 1e-4,
        device: str | None = None,
    ):
        self.num_epochs = num_epochs
        self.batch_size = batch_size
        self.lr = lr
        self.device = torch.device(
            device
            or (
                "cuda"
                if torch.cuda.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )
        )
        self.classes: list[str] = []
        self._backbone: nn.Module | None = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_backbone(self, num_classes: int) -> nn.Module:
        model = timm.create_model(
            "convnextv2_base.fcmae_ft_in22k_in1k",
            pretrained=True,
            num_classes=num_classes,
        )
        return model.to(self.device)

    @property
    def _train_transform(self):
        return transforms.Compose(
            [
                transforms.RandomResizedCrop(self.IMG_SIZE),
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
                transforms.ToTensor(),
                transforms.Normalize(self.MEAN, self.STD),
            ]
        )

    @property
    def _eval_transform(self):
        return transforms.Compose(
            [
                transforms.Resize(int(self.IMG_SIZE * 256 / 224)),
                transforms.CenterCrop(self.IMG_SIZE),
                transforms.ToTensor(),
                transforms.Normalize(self.MEAN, self.STD),
            ]
        )

    # ------------------------------------------------------------------
    # BaseModel interface
    # ------------------------------------------------------------------

    def finetune(self, samples: list[dict], classes: list[str]) -> dict:
        self.classes = classes
        self._backbone = self._build_backbone(len(classes))

        dataset = _ImageDataset(samples, classes, self._train_transform)
        # num_workers > 0 hangs on macOS MPS; pin_memory is unsupported there too
        on_mps = self.device.type == "mps"
        loader = DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=0 if on_mps else 4,
            pin_memory=not on_mps,
        )

        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.AdamW(
            self._backbone.parameters(), lr=self.lr, weight_decay=1e-2
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=self.num_epochs
        )

        self._backbone.train()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0

        with Progress(
            TextColumn("[bold cyan]Epoch {task.fields[epoch]}/{task.fields[total_epochs]}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("loss={task.fields[loss]:.4f} acc={task.fields[acc]:.3f}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            epoch_task = progress.add_task(
                "training",
                total=self.num_epochs * len(loader),
                epoch=1,
                total_epochs=self.num_epochs,
                loss=0.0,
                acc=0.0,
            )

            for epoch in range(1, self.num_epochs + 1):
                progress.update(epoch_task, epoch=epoch)
                epoch_loss = 0.0
                epoch_correct = 0
                epoch_samples = 0

                for images, labels in loader:
                    images = images.to(self.device)
                    labels = labels.to(self.device)

                    optimizer.zero_grad()
                    logits = self._backbone(images)
                    loss = criterion(logits, labels)
                    loss.backward()
                    optimizer.step()

                    epoch_loss += loss.item() * images.size(0)
                    preds = (torch.sigmoid(logits) > 0.5).float()
                    epoch_correct += (preds == labels).all(dim=1).sum().item()
                    epoch_samples += images.size(0)

                    progress.update(
                        epoch_task,
                        advance=1,
                        loss=epoch_loss / max(epoch_samples, 1),
                        acc=epoch_correct / max(epoch_samples, 1),
                    )

                total_loss += epoch_loss
                total_correct += epoch_correct
                total_samples += epoch_samples
                scheduler.step()

        avg_loss = total_loss / max(total_samples, 1)
        accuracy = total_correct / max(total_samples, 1)
        return {"loss": avg_loss, "accuracy": accuracy}

    def predict(self, image_paths: list[Path]) -> list[Prediction]:
        if self._backbone is None or not self.classes:
            raise RuntimeError(
                "Model has no weights. Call finetune() or load() first."
            )

        self._backbone.eval()
        transform = self._eval_transform
        predictions: list[Prediction] = []

        with torch.no_grad():
            for path in image_paths:
                image = Image.open(path).convert("RGB")
                tensor = transform(image).unsqueeze(0).to(self.device)
                probs = torch.sigmoid(self._backbone(tensor)).squeeze(0).cpu()

                indices = (probs > 0.5).nonzero(as_tuple=True)[0].tolist()
                if not indices:
                    # Fall back to argmax when nothing clears the threshold
                    indices = [int(probs.argmax().item())]

                indices.sort(key=lambda i: probs[i].item(), reverse=True)
                predictions.append(
                    Prediction(
                        path=str(path),
                        labels=[self.classes[i] for i in indices],
                        confidences=[round(probs[i].item(), 4) for i in indices],
                    )
                )

        return predictions

    def save(self, path: Path) -> None:
        if self._backbone is None:
            raise RuntimeError("No model to save.")
        torch.save(
            {
                "state_dict": self._backbone.state_dict(),
                "classes": self.classes,
                "config": {
                    "num_epochs": self.num_epochs,
                    "batch_size": self.batch_size,
                    "lr": self.lr,
                },
            },
            path,
        )

    def load(self, path: Path) -> None:
        checkpoint = torch.load(path, weights_only=True, map_location=self.device)
        self.classes = checkpoint["classes"]
        cfg = checkpoint.get("config", {})
        self.num_epochs = cfg.get("num_epochs", self.num_epochs)
        self.batch_size = cfg.get("batch_size", self.batch_size)
        self.lr = cfg.get("lr", self.lr)
        self._backbone = self._build_backbone(len(self.classes))
        self._backbone.load_state_dict(checkpoint["state_dict"])