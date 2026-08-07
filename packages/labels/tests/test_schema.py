"""The schema descriptor: what it stores, what it refuses, and what it answers."""

import pytest
from pydantic import ValidationError

from strata.labels import (
    Choices,
    ChoicesPrediction,
    ClassificationSchema,
    SchemaError,
)


@pytest.fixture
def schema():
    return ClassificationSchema(classes=["cat", "dog", "bird"])


# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------


def test_a_schema_round_trips_through_json(schema):
    assert ClassificationSchema.model_validate_json(schema.model_dump_json()) == schema


def test_class_order_survives_a_round_trip():
    # Checkpoints map output neurons to this list by position, so order is
    # data rather than presentation
    classes = ["dog", "cat", "bird"]
    restored = ClassificationSchema.model_validate({"classes": classes})
    assert restored.classes == classes


def test_the_task_discriminator_is_stored(schema):
    assert schema.model_dump()["task"] == "classification"


def test_multiple_defaults_to_true():
    assert ClassificationSchema(classes=["cat"]).multiple is True


def test_empty_class_names_are_refused():
    with pytest.raises(ValidationError, match="cannot be empty"):
        ClassificationSchema(classes=["cat", "  "])


def test_duplicate_classes_are_refused():
    with pytest.raises(ValidationError, match="Duplicate"):
        ClassificationSchema(classes=["cat", "dog", "cat"])


def test_a_schema_with_no_classes_is_allowed():
    # A label set exists before anyone has decided what is in it
    assert ClassificationSchema().classes == []


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def test_a_value_within_the_class_list_validates(schema):
    schema.validate_value(Choices(values=["cat", "dog"]))


def test_an_empty_value_validates(schema):
    schema.validate_value(Choices())


def test_a_class_outside_the_list_is_refused(schema):
    with pytest.raises(SchemaError, match="fish"):
        schema.validate_value(Choices(values=["cat", "fish"]))


def test_the_error_names_what_is_known(schema):
    with pytest.raises(SchemaError, match="known: cat, dog, bird"):
        schema.validate_value(Choices(values=["fish"]))


def test_a_single_choice_schema_refuses_two(schema):
    single = ClassificationSchema(classes=["cat", "dog"], multiple=False)
    with pytest.raises(SchemaError, match="single-choice"):
        single.validate_value(Choices(values=["cat", "dog"]))


def test_a_single_choice_schema_accepts_one():
    single = ClassificationSchema(classes=["cat", "dog"], multiple=False)
    single.validate_value(Choices(values=["cat"]))


def test_a_repeated_class_is_refused(schema):
    with pytest.raises(SchemaError, match="Repeated"):
        schema.validate_value(Choices(values=["cat", "cat"]))


def test_validation_reads_the_schema_not_the_value(schema):
    # The value type cannot enforce this itself: the class list lives on the
    # schema, which the value knows nothing about
    assert Choices(values=["fish"]).values == ["fish"]


# ----------------------------------------------------------------------
# The indexing contract
# ----------------------------------------------------------------------


def test_classes_asserted_is_what_the_catalog_indexes(schema):
    assert schema.classes_asserted(Choices(values=["cat", "dog"])) == {"cat", "dog"}


def test_an_empty_value_asserts_nothing(schema):
    assert schema.classes_asserted(Choices()) == set()


def test_classes_asserted_answers_for_a_prediction_too(schema):
    prediction = ChoicesPrediction(values=["cat"], confidences=[0.9])
    assert schema.classes_asserted(prediction) == {"cat"}


def test_the_schema_does_not_rank(schema):
    # Confidences are carried; how to order on them is an active-learning
    # strategy, and that belongs to the labeller
    assert not hasattr(schema, "score")
    assert not hasattr(schema, "uncertainty")
