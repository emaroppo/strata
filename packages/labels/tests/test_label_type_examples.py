"""Every label type, as far as this package alone can check it.

The rest of each type's journey — the catalog, modelling, Label Studio — is
tested in the package that owns each layer, against the same examples. See
``strata.labels.examples``.

These exist because of how the failures look. A value serialises happily
whatever it is, and read back as the wrong type it parses without complaint
into something empty: pydantic drops the fields it does not recognise. So a
corpus could be annotated with boxes and hand back nothing, and the only
symptom was a number quietly lower than it should be.
"""

from typing import get_args

import pytest
from pydantic import TypeAdapter

from strata.labels import (
    MANIFEST_FORMAT,
    MANIFEST_NAME,
    AnyPrediction,
    AnySchema,
    AnyValue,
    Manifest,
    ManifestSample,
    Prediction,
)
from strata.labels.examples import EXAMPLES

_VALUE = TypeAdapter(AnyValue)
_PREDICTION = TypeAdapter(AnyPrediction)
_SCHEMA = TypeAdapter(AnySchema)

each_type = pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.name)


def _members(union) -> set[type]:
    # Annotated[A | B | C, Field(discriminator=...)]
    return set(get_args(get_args(union)[0]))


def test_every_label_type_has_an_example():
    """What lets every other package test every type without being told about it."""
    assert _members(AnyValue) == {type(e.value) for e in EXAMPLES}
    assert _members(AnySchema) == {type(e.schema) for e in EXAMPLES}
    assert _members(AnyPrediction) == {type(e.prediction) for e in EXAMPLES}


@each_type
def test_a_value_reads_back_as_itself(example):
    assert _VALUE.validate_json(example.value.model_dump_json()) == example.value


@each_type
def test_a_schema_reads_back_as_itself(example):
    assert _SCHEMA.validate_json(example.schema.model_dump_json()) == example.schema


@each_type
def test_a_prediction_reads_back_as_itself(example):
    back = _PREDICTION.validate_json(example.prediction.model_dump_json())
    assert back == example.prediction
    # The confidences are what a review queue is ordered by. Parsing a
    # prediction as a plain value keeps the answer and loses them, which
    # reorders the queue rather than failing.
    assert back.confidences == example.prediction.confidences


@each_type
def test_a_prediction_is_model_output(example):
    # So code can ask, rather than infer from which fields are present
    assert isinstance(example.prediction, Prediction)


@each_type
def test_a_prediction_carries_a_confidence_per_thing_asserted(example):
    assert len(example.prediction.confidences) == len(example.prediction.values)


@each_type
def test_a_manifest_carries_the_type(example, tmp_path):
    manifest = Manifest(
        format=MANIFEST_FORMAT,
        dataset="d",
        label_set="x",
        label_schema=example.schema,
        samples=[
            ManifestSample(checksum="a" * 64, path="files/a", split="train", value=example.value)
        ],
    )
    path = tmp_path / MANIFEST_NAME
    path.write_text(manifest.model_dump_json())

    # A dataset version is the artifact a model trains from, and it has to
    # survive being written to disk and read on another machine
    back = Manifest.model_validate_json(path.read_text())
    assert back.label_schema == example.schema
    assert back.samples[0].value == example.value
