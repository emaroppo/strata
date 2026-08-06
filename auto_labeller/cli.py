import importlib
import json
import random
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
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


def _push_with_progress(client, project_id, predictions, task_id_map, **kwargs) -> int:
    total = sum(1 for p in predictions if p.path in task_id_map)
    with Progress(
        TextColumn("[bold cyan]Pushing"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        bar = progress.add_task("push", total=total)
        return client.push_predictions(
            project_id,
            predictions,
            task_id_map,
            on_progress=lambda n: progress.advance(bar, n),
            **kwargs,
        )


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
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
) -> None:
    """Scan images_dir for new images and add them to the dataset JSON.

    Label Studio tasks are created on demand by `push`, so new images only
    need to be registered here.
    """
    from .dataset import Sample, load_dataset, save_dataset

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

    updated = dataset + new_samples
    save_dataset(updated, settings.paths.dataset)
    console.print(
        f"[green]Added {len(new_samples)} new images "
        f"({len(updated)} total samples)[/green]"
    )


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
    samples = (
        split_labeled_unlabeled(dataset)[1]
        if unlabeled_only
        else [s for s in dataset if not s.skipped]
    )

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
    refresh: bool = typer.Option(False, "--refresh/--no-refresh", help="Replace existing predictions instead of skipping those tasks"),
    limit: int | None = typer.Option(None, help="Push only the top-N predictions (most uncertain first when prioritized)"),
    sample: int | None = typer.Option(None, help="Predict on a random subset of N eligible images instead of all of them"),
    use_cache: bool = typer.Option(True, "--cache/--no-cache", help="Use the local task-id cache (--no-cache forces a full refetch, e.g. after manual prediction changes in LS)"),
) -> None:
    """Push model predictions to Label Studio as pre-annotations."""
    from .active_learning import rank_by_uncertainty
    from .dataset import Sample, load_dataset, split_labeled_unlabeled
    from .ls_client import LSClient
    from .predict import run_predictions

    settings = Settings.load(config_path)
    model = _load_model(settings)

    ckpt = _resolve_checkpoint(model, settings, checkpoint)
    if not ckpt:
        console.print("[red]No checkpoint found. Run 'train' first or pass --checkpoint.[/red]")
        raise typer.Exit(1)
    console.print(f"Using checkpoint: {ckpt}")

    client = LSClient(settings)
    with console.status("Fetching task list from Label Studio (slow on large projects)..."):
        task_id_map = client.get_task_id_map(project_id, use_cache=use_cache)
        if refresh:
            already_predicted: set[str] = set()
        else:
            unpredicted = client.get_task_id_map(
                project_id, exclude_predicted=True, use_cache=use_cache
            )
            already_predicted = set(task_id_map) - set(unpredicted)

    dataset = load_dataset(settings.paths.dataset)
    samples = (
        split_labeled_unlabeled(dataset)[1]
        if unlabeled_only
        else [s for s in dataset if not s.skipped]
    )
    # Images without an LS task are eligible: tasks are created on demand for
    # whatever makes the final cut. Without --refresh, skip what's already
    # pushed so an interrupted push can resume without re-predicting.
    samples = [s for s in samples if s.path not in already_predicted]
    if not samples:
        console.print("[yellow]Nothing to push — all eligible images have predictions.[/yellow]")
        raise typer.Exit(0)

    if sample is not None and len(samples) > sample:
        # Fresh subset each run so successive rounds see different candidates
        samples = random.sample(samples, sample)
        console.print(f"Sampled {sample} of the eligible images")

    predictions = run_predictions(model, samples)
    if prioritize_uncertain:
        predictions = rank_by_uncertainty(predictions)
    if limit is not None:
        predictions = predictions[:limit]

    missing = [p for p in predictions if p.path not in task_id_map]
    if missing:
        console.print(f"Creating {len(missing)} new tasks in Label Studio...")
        client.import_tasks(project_id, [Sample(path=p.path) for p in missing])
        task_id_map = client.get_task_id_map(project_id, use_cache=use_cache)

    num_pushed = _push_with_progress(
        client,
        project_id,
        predictions,
        task_id_map,
        model_version=ckpt.stem,
        replace_existing=refresh,
    )

    skipped = len(predictions) - num_pushed
    console.print(
        f"[green]Pushed {num_pushed} predictions to project {project_id} "
        f"(model version: {ckpt.stem})[/green]"
        + (f" [dim]({skipped} tasks already had predictions)[/dim]" if skipped else "")
    )


@app.command(name="export")
def export_annotations(
    project_id: int = typer.Argument(..., help="Label Studio project ID"),
    config_path: Path = typer.Option("config.toml", help="Path to config file"),
    output: Path | None = typer.Option(None, help="Output path (defaults to dataset path)"),
) -> None:
    """Export corrected annotations from Label Studio back to the dataset."""
    from .dataset import load_dataset, save_dataset
    from .ls_client import LSClient

    settings = Settings.load(config_path)
    client = LSClient(settings)

    with console.status("Exporting annotations from Label Studio (slow on large projects)..."):
        exported = client.export_annotations(project_id)

    # Merge: LS only holds a subset of the dataset (tasks are created on
    # demand), so overwriting would drop every image without a task
    out_path = output or settings.paths.dataset
    samples = list(exported)
    if out_path.exists():
        by_path = {e.path: e for e in exported}
        existing = load_dataset(out_path)
        samples = [by_path.get(s.path, s) for s in existing]
        known = {s.path for s in existing}
        samples += [e for e in exported if e.path not in known]
    save_dataset(samples, out_path)

    labeled = [s for s in samples if s.is_labeled]
    console.print(
        f"[green]Merged {len(exported)} exported tasks into {out_path} "
        f"({len(samples)} samples, {len(labeled)} labeled)[/green]"
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
    if meta.get("num_skipped") is not None:
        table.add_row("Skipped samples", str(meta["num_skipped"]))
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
