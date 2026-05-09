from label_studio_sdk.client import LabelStudio

from .config import Settings
from .dataset import Sample
from .model import Prediction


class LSClient:
    def __init__(self, settings: Settings):
        self.client = LabelStudio(
            base_url=settings.label_studio.url,
            api_key=settings.label_studio.api_key,
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
                image_url = f"/data/local-files/?d=images/{path}"
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
        self.client.projects.import_tasks(id=project_id, request=tasks)

    def push_predictions(
        self,
        project_id: int,
        predictions: list[Prediction],
        task_id_map: dict[str, int],
    ) -> None:
        for pred in predictions:
            task_id = task_id_map.get(pred.path)
            if task_id is None:
                continue
            self.client.predictions.create(
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
            )

    def export_annotations(self, project_id: int) -> list[Sample]:
        tasks = self.client.tasks.list(project=project_id)
        samples: list[Sample] = []
        for task in tasks:
            image_path = task.data.get("image", "")
            if "local-files" in image_path:
                image_path = "data/" + image_path.split("d=images/")[-1]

            labels: list[str] = []
            if task.annotations:
                latest = task.annotations[-1]
                raw_results = (
                    latest.get("result", [])
                    if isinstance(latest, dict)
                    else (latest.result or [])
                )
                for result in raw_results:
                    r_type = result.get("type") if isinstance(result, dict) else result.type
                    r_value = result.get("value", {}) if isinstance(result, dict) else result.value
                    if r_type == "choices":
                        labels.extend(r_value.get("choices", []))

            samples.append(Sample(path=image_path, labels=labels))
        return samples

    def get_task_id_map(self, project_id: int) -> dict[str, int]:
        tasks = self.client.tasks.list(project=project_id)
        mapping: dict[str, int] = {}
        for task in tasks:
            image_path = task.data.get("image", "")
            if "local-files" in image_path:
                image_path = "data/" + image_path.split("d=images/")[-1]
            mapping[image_path] = task.id
        return mapping

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
