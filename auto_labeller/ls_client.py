import json
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, unquote

from label_studio_sdk import PredictionRequest
from label_studio_sdk.client import LabelStudio

from .config import Settings
from .dataset import Sample
from .model import Prediction


class LSClient:
    def __init__(self, settings: Settings):
        self.client = LabelStudio(
            base_url=settings.label_studio.url,
            api_key=settings.label_studio.api_key,
            # Bulk imports on large projects can exceed the SDK's 60s default
            timeout=300,
        )
        self.settings = settings

    def create_project(self, name: str, classes: list[str]) -> int:
        choices = "\n".join(f'    <Choice value="{c}" />' for c in classes)
        label_config = (
            "<View>\n"
            '  <Image name="image" value="$image" />\n'
            '  <Choices name="label" toName="image" choice="multiple">\n'
            f"{choices}\n"
            "  </Choices>\n"
            "</View>"
        )
        project = self.client.projects.create(
            title=name,
            label_config=label_config,
        )
        return project.id

    def import_tasks(
        self,
        project_id: int,
        samples: list[Sample],
        images_base_url: str = "",
    ) -> None:
        tasks: list[dict] = []
        for s in samples:
            if images_base_url:
                image_url = f"{images_base_url}/{s.path}"
            else:
                # Strip the leading 'data/' because ./data is mounted as images/ in the container
                path = s.path.removeprefix("data/")
                # Percent-encode so characters like '&' or '#' don't break the query string
                image_url = f"/data/local-files/?d=images/{quote(path)}"
            task: dict = {"data": {"image": image_url}}
            if s.is_labeled:
                task["annotations"] = [
                    {
                        "result": [
                            {
                                "from_name": "label",
                                "to_name": "image",
                                "type": "choices",
                                "value": {"choices": s.labels},
                            }
                        ]
                    }
                ]
            tasks.append(task)
        resp = self.client.projects.import_tasks(
            id=project_id, request=tasks, return_task_ids=True
        )
        # task_ids is untyped but present with return_task_ids; keep the
        # local cache current so the next push needs no full task listing
        task_ids = (resp.model_extra or {}).get("task_ids") or []
        cache = self._load_task_map_cache(project_id)
        if cache is not None and len(task_ids) == len(samples):
            for s, task_id in zip(samples, task_ids):
                cache[s.path] = [task_id, False]
            self._save_task_map_cache(project_id, cache)

    def push_predictions(
        self,
        project_id: int,
        predictions: list[Prediction],
        task_id_map: dict[str, int],
        model_version: str | None = None,
        replace_existing: bool = False,
        on_progress: Callable[[int], None] | None = None,
        chunk_size: int = 200,
    ) -> int:
        """Bulk-import predictions. Returns the number pushed.

        With replace_existing, old predictions on the target tasks are
        bulk-deleted first instead of accumulating duplicates.
        """
        to_push = [
            (pred, task_id_map[pred.path])
            for pred in predictions
            if pred.path in task_id_map
        ]
        if not to_push:
            return 0

        if replace_existing:
            self.client.actions.create(
                id="delete_tasks_predictions",
                project=project_id,
                selected_items={"all": False, "included": [tid for _, tid in to_push]},
            )

        requests = [
            PredictionRequest(
                task=task_id,
                result=[
                    {
                        "from_name": "label",
                        "to_name": "image",
                        "type": "choices",
                        "value": {"choices": pred.labels},
                    }
                ],
                score=max(pred.confidences) if pred.confidences else 0.0,
                model_version=model_version,
            )
            for pred, task_id in to_push
        ]
        for i in range(0, len(requests), chunk_size):
            chunk = requests[i : i + chunk_size]
            self.client.projects.import_predictions(id=project_id, request=chunk)
            if on_progress is not None:
                on_progress(len(chunk))

        if model_version is not None:
            # LS only displays predictions whose version matches the project's
            # active model version, so keep it pointed at what we just pushed
            self.client.projects.update(id=project_id, model_version=model_version)

        cache = self._load_task_map_cache(project_id)
        if cache is not None:
            for pred, _task_id in to_push:
                if pred.path in cache:
                    cache[pred.path][1] = True
            self._save_task_map_cache(project_id, cache)
        return len(to_push)

    @staticmethod
    def _url_to_path(image_url: str) -> str:
        if "local-files" in image_url:
            return "data/" + unquote(image_url.split("d=images/")[-1])
        return image_url

    def export_annotations(self, project_id: int) -> list[Sample]:
        # Snapshot export is one bulk download instead of paging through tasks;
        # the timeout is how long we wait for LS to prepare the snapshot
        tasks = self.client.projects.exports.as_json(project_id, timeout=600)
        samples: list[Sample] = []
        for task in tasks:
            image_path = self._url_to_path(task.get("data", {}).get("image", ""))

            labels: list[str] = []
            skipped = False
            annotations = task.get("annotations") or []
            if annotations:
                latest = annotations[-1]
                if latest.get("was_cancelled"):
                    # Skipped: reviewed but no class fits. The cancelled
                    # annotation snapshots the pre-annotation (a model guess),
                    # so its choices are not labels.
                    skipped = True
                else:
                    for result in latest.get("result") or []:
                        if result.get("type") == "choices":
                            labels.extend(result.get("value", {}).get("choices", []))

            samples.append(Sample(path=image_path, labels=labels, skipped=skipped))
        return samples

    # ------------------------------------------------------------------
    # Task-id map + local cache
    #
    # Listing every task takes minutes on large projects, so we keep a
    # local {path: [task_id, has_prediction]} cache. It is extended on
    # import, updated on push, and rebuilt whenever the project's task
    # count no longer matches (e.g. tasks added/deleted in the LS UI).
    # Prediction changes made manually in LS are NOT detected; pass
    # use_cache=False (CLI: --no-cache) to force a full refetch.
    # ------------------------------------------------------------------

    def _task_map_cache_path(self, project_id: int) -> Path:
        return self.settings.paths.dataset.parent / f"task_map_{project_id}.json"

    def _load_task_map_cache(self, project_id: int) -> dict[str, list] | None:
        path = self._task_map_cache_path(project_id)
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def _save_task_map_cache(self, project_id: int, cache: dict[str, list]) -> None:
        path = self._task_map_cache_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(cache, f)

    def get_task_id_map(
        self,
        project_id: int,
        exclude_predicted: bool = False,
        use_cache: bool = True,
    ) -> dict[str, int]:
        if use_cache:
            cache = self._load_task_map_cache(project_id)
            if cache is not None:
                total = self.client.projects.get(id=project_id).task_number or 0
                if total == len(cache):
                    return {
                        path: entry[0]
                        for path, entry in cache.items()
                        if not (exclude_predicted and entry[1])
                    }

        tasks = self.client.tasks.list(
            project=project_id,
            page_size=1000,
            fields="task_only",
            resolve_uri=False,
        )
        cache = {}
        for task in tasks:
            path = self._url_to_path(task.data.get("image", ""))
            cache[path] = [task.id, (task.total_predictions or 0) > 0]
        self._save_task_map_cache(project_id, cache)

        return {
            path: entry[0]
            for path, entry in cache.items()
            if not (exclude_predicted and entry[1])
        }

    def setup_local_storage(self, project_id: int) -> None:
        container_path = self.settings.label_studio.local_storage_path
        self.client.import_storage.local.create(
            project=project_id,
            path=container_path,
            title="Local Images",
            use_blob_urls=False,
        )

    def add_ml_backend(
        self,
        project_id: int,
        url: str = "http://host.docker.internal:9090",
        name: str = "auto-labeller",
    ) -> None:
        self.client.ml.create(project=project_id, url=url, title=name)
