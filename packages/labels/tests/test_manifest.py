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
