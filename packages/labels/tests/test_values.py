"""Annotation payloads: round trips, and what the types refuse."""

import pytest
from pydantic import ValidationError

from strata.labels import (
    Box,
    Boxes,
    BoxesPrediction,
    Choices,
    ChoicesPrediction,
    Span,
    SpansPrediction,
)


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


def test_a_misnamed_field_is_refused():
    """Because the default is to ignore it, and the result would be an answer.

    Every value type calls its payload ``values``. Reaching for ``boxes``
    on a :class:`Boxes` is the obvious mistake, and with pydantic's default
    it builds successfully — empty. Empty is not nothing here: it is a
    reviewer saying none of the classes are present. The typo would be
    stored as that, and read back as that, with nothing to notice it.
    """
    with pytest.raises(ValidationError):
        Boxes(boxes=[Box(label="cat", x=0.1, y=0.1, width=0.2, height=0.2)])
    with pytest.raises(ValidationError):
        Choices(labels=["cat"])


def test_the_right_field_still_works():
    assert Choices(values=["cat"]).values == ["cat"]


# ----------------------------------------------------------------------
# Confidences are positional, for every prediction type
# ----------------------------------------------------------------------


def test_every_prediction_type_refuses_a_mismatch():
    """The guard lived on ChoicesPrediction alone.

    So a detector returning three boxes and one confidence was accepted,
    and the confidences quietly belonged to the wrong boxes. The bbox
    schema ranks the review queue off these numbers, so the queue came out
    ordered by another box's score with nothing raised anywhere.
    """
    box = Box(label="cat", x=0.1, y=0.1, width=0.2, height=0.2)
    with pytest.raises(ValidationError, match="positional"):
        BoxesPrediction(values=[box, box, box], confidences=[0.9])
    with pytest.raises(ValidationError, match="positional"):
        SpansPrediction(
            values=[Span(label="name", start=0, end=4)], confidences=[0.1, 0.2]
        )
    with pytest.raises(ValidationError, match="positional"):
        ChoicesPrediction(values=["cat", "dog"], confidences=[0.9])


def test_confidences_may_be_omitted_by_any_type():
    # A model that reports no confidence at all is not a mismatch
    box = Box(label="cat", x=0.1, y=0.1, width=0.2, height=0.2)
    assert BoxesPrediction(values=[box]).confidences == []


def test_a_confidence_follows_its_span_through_the_sort():
    """Spans sort themselves; confidences have to travel with them.

    Sorting the values alone reassigned every confidence to whichever span
    landed in its place — lengths still matched, so no guard could see it.
    """
    prediction = SpansPrediction(
        values=[Span(label="last", start=10, end=12), Span(label="first", start=0, end=2)],
        confidences=[0.1, 0.9],
    )
    assert [(s.label, c) for s, c in zip(prediction.values, prediction.confidences)] == [
        ("first", 0.9),
        ("last", 0.1),
    ]
