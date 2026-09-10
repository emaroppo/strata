"""The manifest: a materialised dataset's description of itself.

Written beside the files, and complete enough that nothing needs a database
to train from it. That is what makes a dataset version the portable unit —
the property ``project.py`` used to claim for a whole project directory, at
a granularity that survives the move to a catalog.

**The one file two packages have to agree on.** The catalog writes it and
modelling reads it, and neither may import the other. So the definition
lives here, where both can, rather than in the writer with the reader
reconstructing it from key names — which it did, and which meant a renamed
field read back as nothing instead of failing.

**It says which format it is.** The writer states ``format`` and every read
checks it, because once the packages ship separately the release that wrote
a manifest need not be the one reading it. The number goes up only when an
older reader would *misread* a newer file — a field whose meaning changed, a
value it would take for something else. A field added with a default does
not bump it: pydantic ignores fields it does not know, which is exactly why
that case is safe and the other one is not.

Sample ids are catalog-local, so ``checksum`` travels with them: files and
labels alone are enough to train anywhere, and the checksum is what lets a
different catalog match these samples to its own.
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

    id: int
    checksum: str
    #: Relative to the manifest's own directory, so the whole thing moves.
    path: str
    #: Shared by samples that must not straddle the split; null means the
    #: sample is its own group.
    group_id: str | None = None
    #: Which side of the split. Three names rather than a flag, because a
    #: flag has no room for a third: a held-out sample that a reader took
    #: for "not validation" would be trained on — silently, and on exactly
    #: the samples kept back to be measured on honestly.
    #:
    #: ``holdout`` never reaches a model, in training or in validation.
    #: Nothing assigns it yet; the layout has room for it so that the first
    #: holdout does not have to be a new format.
    split: Literal["train", "val", "holdout"]
    #: Null when the sample was skipped. An empty value is different: a
    #: human looked and found nothing, which is an answer.
    #:
    #: Any annotation payload, not one task's — a dataset version is the
    #: artifact a model trains from, so pinning it to choices would mean no
    #: detector could ever be handed one.
    value: AnyValue | None = None
    #: What the model is told about this sample beyond its bytes, by the
    #: name the project gave each one.
    #:
    #: Deliberately plain JSON rather than ``AnyValue``. That union is
    #: choices, spans and boxes — a coordinate pair is none of them, and a
    #: feature read from a metadata key has no label shape at all. Typing
    #: it as a label value would make the label-set source the only one
    #: expressible, which is the corner worth not painting into.
    features: dict[str, Any] = Field(default_factory=dict)


class Manifest(BaseModel):
    """A dataset version, in full."""

    #: Required rather than defaulted: a default would read a manifest that
    #: predates the field as the current layout, which is the one guess
    #: this field exists to stop.
    format: int
    dataset: str
    version: int
    #: Which catalog this was built from. A dataset name and a sample id
    #: both mean something only within one, so a directory that does not
    #: say makes a run's lineage unresolvable the moment a host serves two.
    #: Null for a version materialised before catalogs had identities.
    catalog_id: str | None = None
    label_set: str
    label_schema: AnySchema
    #: What was asked for, and what grouping actually allowed. They differ
    #: when a group is too large to hold out at the requested ratio.
    val_ratio: float = 0.2
    val_ratio_achieved: float = 0.0
    #: The feature declarations this version was built under, as
    #: ``{name, source, ref}``. Recorded so a materialised directory still
    #: says where its features came from once it is somewhere else.
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
    """A stable digest of one sample's features.

    What makes a cached prediction honest. A prediction is a function of a
    checkpoint, some bytes *and these values*; keyed on the first two alone
    it survives a correction to the third and is served for inputs that no
    longer exist. Widening the key is what lets the cache keep its stated
    property — nothing is ever invalidated — while ceasing to be wrong.

    Here rather than beside the feature declarations because two hosts
    compute it and a third stores it: the laptop keys its lookups with it,
    the modelling host its answers, and the prediction cache holds both. A
    digest that differed between them would not be wrong, only a cache that
    never hits — which is why the test pins its output rather than its
    properties.

    The empty digest is empty rather than a hash of nothing, so a project
    with no features reads exactly as it did before there were any.
    """
    if not features:
        return ""
    canonical = json.dumps(features, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
