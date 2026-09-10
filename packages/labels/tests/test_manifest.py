"""The manifest, and the digest the prediction cache keys on."""

import json

import pytest

from strata.labels import (
    MANIFEST_FORMAT,
    ClassificationSchema,
    Manifest,
    ManifestFormatError,
    feature_digest,
)


def _fields(**overrides) -> dict:
    fields = {
        "format": MANIFEST_FORMAT,
        "dataset": "d",
        "version": 1,
        "label_set": "x",
        "label_schema": {"task": "classification", "classes": ["a"]},
    }
    fields.update(overrides)
    return fields


def test_a_manifest_says_which_format_it_is():
    manifest = Manifest(**_fields(label_schema=ClassificationSchema(classes=["a"])))
    written = json.loads(manifest.model_dump_json())
    assert written["format"] == MANIFEST_FORMAT
    assert Manifest.model_validate_json(manifest.model_dump_json()) == manifest


def test_a_manifest_that_does_not_say_is_refused():
    """Every manifest written before the field existed.

    Read as the current layout, a sample the old writer marked one way
    could be taken for another — so it is refused, naming the way out.
    """
    fields = _fields()
    del fields["format"]
    with pytest.raises(ManifestFormatError, match="materialise the dataset version again"):
        Manifest.model_validate_json(json.dumps(fields))


def test_a_format_this_release_does_not_read_is_refused():
    with pytest.raises(ManifestFormatError, match=f"format 2.*reads format {MANIFEST_FORMAT}"):
        Manifest.model_validate_json(json.dumps(_fields(format=2)))


def test_the_samples_divide_three_ways():
    samples = [
        {"id": i, "checksum": f"{i:064d}", "path": f"files/{i}", "split": split}
        for i, split in enumerate(["train", "train", "val", "holdout"])
    ]
    manifest = Manifest.model_validate(_fields(samples=samples))
    assert [s.id for s in manifest.train] == [0, 1]
    assert [s.id for s in manifest.val] == [2]
    assert [s.id for s in manifest.holdout] == [3]


def test_a_sample_must_say_which_side_it_is_on():
    """No default: a missing split read as "train" is how a holdout gets trained on."""
    sample = {"id": 0, "checksum": "0" * 64, "path": "files/0"}
    with pytest.raises(ValueError, match="split"):
        Manifest.model_validate(_fields(samples=[sample]))


def test_a_refusal_is_not_a_validation_error():
    """Stale and broken need telling apart: the first is rebuilt, the second is a bug."""
    assert not issubclass(ManifestFormatError, ValueError)


def test_the_empty_digest_is_empty():
    """A project with no features reads exactly as it did before there were any."""
    assert feature_digest({}) == ""
    assert feature_digest(None) == ""
    assert feature_digest({"a": 1}) != ""


def test_the_digest_does_not_depend_on_key_order():
    assert feature_digest({"a": 1, "b": 2}) == feature_digest({"b": 2, "a": 1})
