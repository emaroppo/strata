import importlib
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import Settings
from .model import BaseModel

app = typer.Typer(name="auto-labeller")
console = Console()

_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp", "tiff", "gif"}


def _load_model(settings: Settings) -> BaseModel:
    module = importlib.import_module(settings.model.module)
    model_cls = getattr(module, settings.model.class_name)
    return model_cls()


def _resolve_checkpoint(
    model: BaseModel,
    settings: Settings,
    checkpoint: Path | None = None,
    fresh: bool = False,
) -> Path | None:
    """Load a checkpoint into model. Returns the path loaded, or None."""
    if fresh:
        return None
    if checkpoint is not None:
        model.load(checkpoint)
        return checkpoint
    checkpoint_dir = settings.paths.checkpoints_dir
    if not checkpoint_dir.exists():
        return None
    checkpoints = sorted(checkpoint_dir.glob("round_*.pt"))
    if not checkpoints:
        return None
    latest = checkpoints[-1]
    model.load(latest)
    return latest


# Keep old name for backward compat within this file
def _load_latest_checkpoint(model: BaseModel, settings: Settings) -> Path | None:
    return _resolve_checkpoint(model, settings)


@app.command()
def init(
    name: str = typer.Argument(..., help="Project name in Label Studio"),
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
) -> None:
    """Create a Label Studio project and import tasks from the dataset."""
    from .dataset import get_classes, load_dataset
    from .ls_client import LSClient

    settings = Settings.load(config_path)
    dataset = load_dataset(settings.paths.dataset)
    classes = get_classes(dataset)

    if not classes:
        console.print("[red]No classes found in dataset. Label some samples first.[/red]")
        raise typer.Exit(1)

    client = LSClient(settings)
    project_id = client.create_project(name, classes)
    client.setup_local_storage(project_id)
    client.import_tasks(project_id, dataset)

    console.print(
        f"[green]Created project '{name}' (ID: {project_id}) "
        f"with {len(dataset)} tasks[/green]"
    )
    console.print(f"Classes: {', '.join(classes)}")


@app.command()
def ingest(
    project_id: int = typer.Argument(..., help="Label Studio project ID to add images to"),
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    auto_label: bool = typer.Option(False, "--auto-label/--no-auto-label", help="Push model predictions as pre-annotations"),
    checkpoint: Path | None = typer.Option(None, help="Checkpoint to use for auto-labelling (default: latest)"),
    prioritize_uncertain: bool = typer.Option(True, help="Show most uncertain images first"),
) -> None:
    """Scan images_dir for new images, add them to the dataset, and import to Label Studio."""
    from .dataset import Sample, load_dataset, save_dataset
    from .ls_client import LSClient

    settings = Settings.load(config_path)
    images_dir = settings.paths.images_dir

    if not images_dir.exists():
        console.print(f"[red]images_dir does not exist: {images_dir}[/red]")
        raise typer.Exit(1)

    # Load existing dataset to find already-tracked paths
    dataset: list[Sample] = []
    if settings.paths.dataset.exists():
        dataset = load_dataset(settings.paths.dataset)
    existing_paths = {s.path for s in dataset}

    # Scan for new images
    new_samples: list[Sample] = []
    for path in sorted(images_dir.rglob("*")):
        if path.suffix.lstrip(".").lower() in _IMAGE_EXTENSIONS:
            path_str = str(path)
            if path_str not in existing_paths:
                new_samples.append(Sample(path=path_str))

    if not new_samples:
        console.print("[yellow]No new images found in images_dir.[/yellow]")
        raise typer.Exit(0)

    console.print(f"Found {len(new_samples)} new images.")

    # Persist to dataset
    updated = dataset + new_samples
    save_dataset(updated, settings.paths.dataset)
    console.print(f"[green]Updated dataset ({len(updated)} total samples)[/green]")

    # Import new tasks to Label Studio
    client = LSClient(settings)
    client.import_tasks(project_id, new_samples)
    console.print(f"[green]Imported {len(new_samples)} tasks to project {project_id}[/green]")

    if not auto_label:
        return

    # Auto-label: predict + push
    from .active_learning import rank_by_uncertainty
    from .predict import run_predictions

    model = _load_model(settings)
    ckpt = _resolve_checkpoint(model, settings, checkpoint)
    if not ckpt:
        console.print("[red]No checkpoint found. Run 'train' first or pass --checkpoint.[/red]")
        raise typer.Exit(1)
    console.print(f"Using checkpoint: {ckpt}")

    predictions = run_predictions(model, new_samples)
    if prioritize_uncertain:
        predictions = rank_by_uncertainty(predictions)

    task_id_map = client.get_task_id_map(project_id)
    client.push_predictions(project_id, predictions, task_id_map)
    console.print(f"[green]Pushed {len(predictions)} pre-annotations[/green]")


@app.command()
def train(
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    round_num: int | None = typer.Option(None, help="Round number (auto-detected if omitted)"),
    checkpoint: Path | None = typer.Option(None, help="Checkpoint to continue from (default: latest)"),
    fresh: bool = typer.Option(False, "--fresh/--no-fresh", help="Train from scratch, ignoring existing checkpoints"),
) -> None:
    """Train the model on current labeled data."""
    from .train import run_training

    settings = Settings.load(config_path)
    model = _load_model(settings)

    ckpt = _resolve_checkpoint(model, settings, checkpoint, fresh)
    if ckpt:
        console.print(f"Loaded checkpoint: {ckpt}")
    elif fresh:
        console.print("Training from scratch.")

    console.print("Training...")
    meta = run_training(model, settings, round_num)

    console.print(f"[green]Round {meta['round']} complete[/green]")
    console.print(
        f"  Train: {meta['num_train']}, Val: {meta['num_val']}, "
        f"Unlabeled: {meta['num_unlabeled']}"
    )
    console.print(f"  Classes: {', '.join(meta['classes'])}")
    if meta["metrics"]:
        for k, v in meta["metrics"].items():
            console.print(f"  {k}: {v}")


@app.command()
def predict(
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    unlabeled_only: bool = typer.Option(True, help="Only predict on unlabeled samples"),
    checkpoint: Path | None = typer.Option(None, help="Checkpoint to use (default: latest)"),
    output: Path | None = typer.Option(None, help="Save predictions to JSON"),
) -> None:
    """Run model predictions on the dataset."""
    from .dataset import Sample, load_dataset, save_dataset, split_labeled_unlabeled
    from .predict import run_predictions

    settings = Settings.load(config_path)
    model = _load_model(settings)

    ckpt = _resolve_checkpoint(model, settings, checkpoint)
    if not ckpt:
        console.print("[red]No checkpoint found. Run 'train' first or pass --checkpoint.[/red]")
        raise typer.Exit(1)
    console.print(f"Loaded checkpoint: {ckpt}")

    dataset = load_dataset(settings.paths.dataset)
    samples = split_labeled_unlabeled(dataset)[1] if unlabeled_only else dataset

    if not samples:
        console.print("[yellow]No samples to predict on.[/yellow]")
        raise typer.Exit(0)

    console.print(f"Predicting on {len(samples)} samples...")
    predictions = run_predictions(model, samples)

    for pred in predictions:
        conf = ", ".join(f"{c:.2f}" for c in pred.confidences)
        console.print(f"  {pred.path}: {pred.labels} ({conf})")

    if output:
        pred_samples = [Sample(path=p.path, labels=p.labels) for p in predictions]
        save_dataset(pred_samples, output)
        console.print(f"[green]Saved predictions to {output}[/green]")


@app.command()
def push(
    project_id: int = typer.Argument(..., help="Label Studio project ID"),
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    unlabeled_only: bool = typer.Option(True, help="Only push for unlabeled samples"),
    checkpoint: Path | None = typer.Option(None, help="Checkpoint to use (default: latest)"),
    prioritize_uncertain: bool = typer.Option(True, help="Show uncertain images first"),
) -> None:
    """Push model predictions to Label Studio as pre-annotations."""
    from .active_learning import rank_by_uncertainty
    from .dataset import load_dataset, split_labeled_unlabeled
    from .ls_client import LSClient
    from .predict import run_predictions

    settings = Settings.load(config_path)
    model = _load_model(settings)

    ckpt = _resolve_checkpoint(model, settings, checkpoint)
    if not ckpt:
        console.print("[red]No checkpoint found. Run 'train' first or pass --checkpoint.[/red]")
        raise typer.Exit(1)

    dataset = load_dataset(settings.paths.dataset)
    samples = split_labeled_unlabeled(dataset)[1] if unlabeled_only else dataset

    predictions = run_predictions(model, samples)
    if prioritize_uncertain:
        predictions = rank_by_uncertainty(predictions)

    client = LSClient(settings)
    task_id_map = client.get_task_id_map(project_id)
    client.push_predictions(project_id, predictions, task_id_map)

    console.print(
        f"[green]Pushed {len(predictions)} predictions to project {project_id}[/green]"
    )


@app.command(name="export")
def export_annotations(
    project_id: int = typer.Argument(..., help="Label Studio project ID"),
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    output: Path | None = typer.Option(None, help="Output path (defaults to dataset path)"),
) -> None:
    """Export corrected annotations from Label Studio back to the dataset."""
    from .dataset import save_dataset
    from .ls_client import LSClient

    settings = Settings.load(config_path)
    client = LSClient(settings)

    samples = client.export_annotations(project_id)
    out_path = output or settings.paths.dataset
    save_dataset(samples, out_path)

    labeled = [s for s in samples if s.is_labeled]
    console.print(
        f"[green]Exported {len(samples)} samples "
        f"({len(labeled)} labeled) to {out_path}[/green]"
    )


@app.command()
def serve(
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(9090, help="Port"),
) -> None:
    """Start the ML backend server for Label Studio live predictions."""
    import uvicorn

    console.print(f"Starting ML backend on {host}:{port}")
    console.print("Add this URL as an ML backend in Label Studio:")
    console.print(f"  http://host.docker.internal:{port}")
    uvicorn.run(
        "auto_labeller.ls_backend:app",
        host=host,
        port=port,
        reload=True,
    )


@app.command()
def report(
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    round_num: int | None = typer.Option(None, help="Round number (latest if omitted)"),
) -> None:
    """Show a round summary report."""
    settings = Settings.load(config_path)
    rounds_dir = settings.paths.rounds_dir

    if not rounds_dir.exists():
        console.print("[red]No rounds found. Run 'train' first.[/red]")
        raise typer.Exit(1)

    round_dirs = sorted(
        d for d in rounds_dir.iterdir() if d.is_dir() and d.name.startswith("round_")
    )
    if not round_dirs:
        console.print("[red]No rounds found.[/red]")
        raise typer.Exit(1)

    if round_num is not None:
        round_dir = rounds_dir / f"round_{round_num:03d}"
    else:
        round_dir = round_dirs[-1]

    meta_path = round_dir / "metadata.json"
    if not meta_path.exists():
        console.print(f"[red]No metadata found for {round_dir.name}[/red]")
        raise typer.Exit(1)

    with open(meta_path) as f:
        meta = json.load(f)

    table = Table(title=f"Round {meta['round']} Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Timestamp", meta["timestamp"])
    table.add_row("Training samples", str(meta["num_train"]))
    table.add_row("Validation samples", str(meta["num_val"]))
    table.add_row("Unlabeled samples", str(meta["num_unlabeled"]))
    table.add_row("Classes", ", ".join(meta["classes"]))
    table.add_row("Checkpoint", meta["checkpoint"])

    if meta.get("metrics"):
        for k, v in meta["metrics"].items():
            table.add_row(k, f"{v:.4f}" if isinstance(v, float) else str(v))

    console.print(table)

    if len(round_dirs) > 1 and round_dir == round_dirs[-1]:
        prev_meta_path = round_dirs[-2] / "metadata.json"
        if prev_meta_path.exists():
            with open(prev_meta_path) as f:
                prev_meta = json.load(f)

            console.print(f"\n[bold]Delta vs Round {prev_meta['round']}:[/bold]")
            delta_train = meta["num_train"] - prev_meta["num_train"]
            console.print(f"  Training samples: {'+' if delta_train >= 0 else ''}{delta_train}")

            if meta.get("metrics") and prev_meta.get("metrics"):
                for k in meta["metrics"]:
                    if k in prev_meta["metrics"]:
                        curr = meta["metrics"][k]
                        prev = prev_meta["metrics"][k]
                        if isinstance(curr, (int, float)) and isinstance(prev, (int, float)):
                            delta = curr - prev
                            console.print(f"  {k}: {'+' if delta >= 0 else ''}{delta:.4f}")
