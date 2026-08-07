"""Annotation payloads: round trips, and what the types refuse."""

import pytest
from pydantic import ValidationError

from strata.labels import Choices, ChoicesPrediction


def test_choices_round_trips_through_json():
    value = Choices(values=["cat", "indoor"])
    assert Choices.model_validate_json(value.model_dump_json()) == value


def test_the_kind_discriminator_survives_a_round_trip():
    # What lets a reader recover the right type without being told the task
    assert Choices(values=["cat"]).model_dump()["kind"] == "choices"


def test_an_empty_value_is_valid():
    # A sample a human looked at and found nothing in is a real answer, and
    # only this distinguishes it from one nobody has opened
    assert Choices().values == []


def test_a_value_is_frozen():
    value = Choices(values=["cat"])
    with pytest.raises(ValidationError):
        value.values = ["dog"]


def test_a_prediction_is_a_value_with_confidences():
    prediction = ChoicesPrediction(values=["cat"], confidences=[0.9])
    assert isinstance(prediction, Choices)
    assert prediction.confidences == [0.9]


def test_confidences_must_line_up_with_values():
    # They are positional, so a length mismatch silently misattributes them
    with pytest.raises(ValidationError, match="positional"):
        ChoicesPrediction(values=["cat", "dog"], confidences=[0.9])


def test_a_prediction_may_omit_confidences_entirely():
    assert ChoicesPrediction(values=["cat"]).confidences == []


def test_a_prediction_round_trips_as_itself():
    prediction = ChoicesPrediction(values=["cat", "dog"], confidences=[0.9, 0.4])
    restored = ChoicesPrediction.model_validate_json(prediction.model_dump_json())
    assert restored == prediction
