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
    #: What the catalog recorded about the sample: where it came from, its
    #: frame index, the video it belongs to. Any grouping a split respects
    #: is a key in here, named by the manifest's ``group_by``, so a split
    #: can be drawn again from the directory under another key.
    metadata: dict[str, Any] = Field(default_factory=dict)
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
    #: Which import the label arrived in, kept through a person's
    #: confirmation or correction of it, so a run can say how much of what
    #: it learned from each batch anybody checked. Null for a label nothing
    #: imported.
    batch: str | None = None
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
    #: The metadata key whose values were kept on one side when the sides
    #: were drawn. Null means none: every sample was its own group.
    group_by: str | None = None
    #: The version whose side assignment this one continues. A version
    #: inherits its predecessor's sides and carries this forward; one that
    #: re-split names itself. A warm start reaches back only as far as
    #: this: a model trained on an earlier version may have seen what is
    #: now held out. Null from a producer that does not say.
    sides_from_version: int | None = None
    #: A split the corpus arrived with, as the freeze read it: the metadata
    #: key naming each sample's set, and which of its values were held out
    #: or validation. Null when every side was drawn.
    given_split: dict[str, Any] | None = None
    #: The feature declarations this version was built under, as
    #: ``{name, source, ref}``. Recorded so a materialised directory still
    #: says where its features came from once it is somewhere else.
    #:
    #: Only ``name`` is part of the contract — it is what a model's
    #: ``requires_features`` is checked against. ``source`` and ``ref`` are
    #: the catalog's own account of where it read each one.
    features: list[dict] = Field(default_factory=list)
    samples: list[ManifestSample] = Field(default_factory=list)
    #: Members of the version left out of ``samples``, by checksum, because
    #: a feature they carry is under dispute — two people answered the
    #: label set it reads from differently, and neither answer can be told
    #: to a model as a fact. Back in once someone settles it.
    disputed: list[str] = Field(default_factory=list)

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


#: One letter per side, for a split to travel positionally.
SIDE_LETTERS = {"train": "t", "val": "v", "holdout": "h"}
LETTER_SIDES = {letter: side for side, letter in SIDE_LETTERS.items()}


def sides_string(manifest: Manifest) -> str:
    """The split as realised, one letter per sample in manifest order.

    ``t``, ``v`` or ``h``. Positional, so it is a few kilobytes for a corpus
    of fifty thousand where a checksum per sample would be megabytes — and
    safe only beside :func:`order_digest`, which proves the reader's
    manifest lists the same samples in the same order.
    """
    return "".join(SIDE_LETTERS[sample.split] for sample in manifest.samples)


def sides_from_string(text: str) -> list[str]:
    """The sides a :func:`sides_string` encodes, refusing a letter it does not know."""
    unknown = sorted({c for c in text if c not in LETTER_SIDES})
    if unknown:
        raise ValueError(
            f"A split string holds t, v or h per sample; this one holds {', '.join(unknown)}."
        )
    return [LETTER_SIDES[c] for c in text]


def order_digest(manifest: Manifest) -> str:
    """A digest of the samples' checksums in manifest order.

    Two manifests of one frozen version list the same samples in the same
    order on every host; this is what proves it before anything is applied
    by position. SHA-256 over each checksum followed by a newline.
    """
    digest = hashlib.sha256()
    for sample in manifest.samples:
        digest.update(sample.checksum.encode())
        digest.update(b"\n")
    return digest.hexdigest()


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
