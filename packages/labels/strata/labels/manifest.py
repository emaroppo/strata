"""The manifest: a materialised dataset's description of itself.

Written beside the files, complete enough that nothing needs a database to
train from it. The catalog writes it and modelling reads it, through this
definition. ``format`` goes up only when an older reader would misread a
newer file; a field added with a default does not bump it. See
``docs/adr/0004``.
"""

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .schema import AnySchema
from .values import AnyValue

MANIFEST_NAME = "manifest.json"
FILES_DIR = "files"
#: The layout this release writes, and the only one it reads.
MANIFEST_FORMAT = 1


class ManifestFormatError(Exception):
    """A manifest in a layout this release does not read.

    Deliberately not a ``ValueError``: pydantic would fold that into a
    validation error beside every field it could not parse, and a caller
    holding a directory needs to tell *stale* from *broken* — the first is
    rebuilt, the second is a bug.
    """


class ManifestSample(BaseModel):
    """One sample as a trainer sees it."""

    #: The sample's id in the catalog that wrote this. Null from a producer
    #: that is not a strata catalog: the number means something only inside
    #: one, and nothing that trains reads it — ``checksum`` is the identity
    #: that survives anywhere.
    id: int | None = None
    checksum: str
    #: Relative to the manifest's own directory, so the whole thing moves.
    path: str
    #: Shared by samples that must not straddle the split; null means the
    #: sample is its own group.
    group_id: str | None = None
    #: Which side of the split. ``holdout`` never reaches a model, in
    #: training or in validation. See ``docs/adr/0003``.
    split: Literal["train", "val", "holdout"]
    #: Null when the sample was skipped. An empty value is different: a
    #: human looked and found nothing, which is an answer.
    #:
    #: Any annotation payload, not one task's — a dataset version is the
    #: artifact a model trains from, so pinning it to choices would mean no
    #: detector could ever be handed one.
    value: AnyValue | None = None
    #: Where the label came from — ``human``, ``import`` — as the catalog
    #: recorded it when this version was written.
    source: str | None = None
    #: Whether a person has vouched for the label. False is not a defect:
    #: labels that arrived with a corpus are trusted and trained on. It is a
    #: record, so that a poor result can be read against how much of what it
    #: learned from nobody checked.
    #:
    #: Null where the producer does not say, which is not the same as False.
    reviewed: bool | None = None
    #: What the model is told about this sample beyond its bytes, by the
    #: name the project gave each one. Plain JSON, not ``AnyValue``: a
    #: feature need not have a label shape. See ``docs/adr/0011``.
    features: dict[str, Any] = Field(default_factory=dict)


class Manifest(BaseModel):
    """A dataset version, in full."""

    #: Required rather than defaulted: a default would read a manifest that
    #: predates the field as the current layout, which is the one guess
    #: this field exists to stop.
    format: int
    #: What the data is called. Required of every producer, strata or not:
    #: a warm start looks for the previous run over the same dataset by it.
    dataset: str
    #: Which version of it. Null from a producer that does not version its
    #: data; a run then records none, and ``report`` compares nothing
    #: against it rather than guessing an order.
    version: int | None = None
    #: Which catalog this was built from. A dataset name and a sample id
    #: both mean something only within one, so a directory that does not
    #: say makes a run's lineage unresolvable the moment a host serves two.
    #: Null for a version materialised before catalogs had identities.
    catalog_id: str | None = None
    label_set: str
    label_schema: AnySchema
    #: What was asked for, and what grouping actually allowed. They differ
    #: when a group is too large to hold out at the requested ratio.
    #:
    #: Null when not recorded, rather than defaulted: a default would have a
    #: hand-written manifest claim a 20% split of which none was achieved.
    val_ratio: float | None = None
    val_ratio_achieved: float | None = None
    #: The holdout the same way: what was asked for and what grouping
    #: allowed. Null from a producer that does not hold out, and from every
    #: version written before one could.
    holdout_ratio: float | None = None
    holdout_ratio_achieved: float | None = None
    #: The feature declarations this version was built under, as
    #: ``{name, source, ref}``. Recorded so a materialised directory still
    #: says where its features came from once it is somewhere else.
    #:
    #: Only ``name`` is part of the contract — it is what a model's
    #: ``requires_features`` is checked against. ``source`` and ``ref`` are
    #: the catalog's own account of where it read each one.
    features: list[dict] = Field(default_factory=list)
    samples: list[ManifestSample] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _readable_by_this_release(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "format" not in data:
            raise ManifestFormatError(
                "This manifest does not say which format it is, so it was written "
                "before manifests did. Its layout is not this release's to guess at: "
                "materialise the dataset version again."
            )
        if data["format"] != MANIFEST_FORMAT:
            raise ManifestFormatError(
                f"This manifest is format {data['format']!r}, and this release reads "
                f"format {MANIFEST_FORMAT}. Install a release that reads it, or "
                f"materialise the dataset version again with this one."
            )
        return data

    @property
    def train(self) -> list[ManifestSample]:
        return [s for s in self.samples if s.split == "train"]

    @property
    def val(self) -> list[ManifestSample]:
        return [s for s in self.samples if s.split == "val"]

    @property
    def holdout(self) -> list[ManifestSample]:
        return [s for s in self.samples if s.split == "holdout"]


def feature_digest(features: dict[str, Any] | None) -> str:
    """A stable digest of one sample's features: the third input to a prediction.

    Two hosts compute it and a third stores it, so its output is pinned by
    a test. Empty, not a hash of nothing, for no features. See
    ``docs/adr/0006``.
    """
    if not features:
        return ""
    canonical = json.dumps(features, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
