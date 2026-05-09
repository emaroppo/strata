from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib


@dataclass
class LabelStudioConfig:
    url: str = "http://localhost:8080"
    api_key: str = ""
    local_storage_path: str = "/label-studio/data/images"


@dataclass
class PathsConfig:
    dataset: Path = field(default_factory=lambda: Path("data/dataset.json"))
    images_dir: Path = field(default_factory=lambda: Path("data/raw"))
    checkpoints_dir: Path = field(default_factory=lambda: Path("models"))
    rounds_dir: Path = field(default_factory=lambda: Path("data/rounds"))


@dataclass
class ModelConfig:
    module: str = "my_model"
    class_name: str = "MyModel"


@dataclass
class Settings:
    label_studio: LabelStudioConfig = field(default_factory=LabelStudioConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    model: ModelConfig = field(default_factory=ModelConfig)

    @classmethod
    def load(cls, path: Path = Path("config.toml")) -> "Settings":
        settings = cls()
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
            if "label_studio" in data:
                settings.label_studio = LabelStudioConfig(**data["label_studio"])
            if "paths" in data:
                settings.paths = PathsConfig(
                    **{k: Path(v) for k, v in data["paths"].items()}
                )
            if "model" in data:
                settings.model = ModelConfig(**data["model"])

        api_key = os.environ.get("LABEL_STUDIO_API_KEY")
        if api_key:
            settings.label_studio.api_key = api_key

        return settings
