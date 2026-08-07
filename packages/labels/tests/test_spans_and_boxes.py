"""Span and box values, and the schemas over them.

Both follow the shape ``Choices`` set: a frozen value, a prediction adding
confidences, and a schema that validates against a class list and answers
the indexing contract.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from strata.labels import (
    AnySchema,
    AnyValue,
    BBoxSchema,
    Box,
    Boxes,
    BoxesPrediction,
    Choices,
    SchemaError,
    Span,
    Spans,
    SpanSchema,
    SpansPrediction,
)

# ----------------------------------------------------------------------
# Spans
# ----------------------------------------------------------------------


def test_a_span_round_trips():
    span = Span(label="PER", start=4, end=9, text="Alice")
    assert Span.model_validate_json(span.model_dump_json()) == span


def test_spans_are_sorted_into_reading_order():
    # So a stored annotation and a model's output compare equal when they
    # say the same thing
    spans = Spans(
        values=[Span(label="B", start=10, end=12), Span(label="A", start=0, end=3)]
    )
    assert [s.label for s in spans.values] == ["A", "B"]


def test_two_span_sets_in_different_orders_are_equal():
    first = Spans(values=[Span(label="A", start=0, end=3), Span(label="B", start=5, end=7)])
    second = Spans(values=[Span(label="B", start=5, end=7), Span(label="A", start=0, end=3)])
    assert first == second


def test_a_backwards_range_is_refused():
    with pytest.raises(ValidationError, match="Not a range"):
        Span(label="PER", start=9, end=4)


def test_a_negative_offset_is_refused():
    with pytest.raises(ValidationError, match="Not a range"):
        Span(label="PER", start=-1, end=4)


def test_an_empty_span_is_allowed():
    # A zero-width range is a real thing to annotate: an insertion point
    assert Span(label="PER", start=4, end=4).end == 4


def test_a_span_prediction_carries_confidences():
    prediction = SpansPrediction(
        values=[Span(label="PER", start=0, end=3)], confidences=[0.7]
    )
    assert isinstance(prediction, Spans)
    assert prediction.confidences == [0.7]


def test_span_text_must_match_its_offsets():
    # The offsets are authoritative, so a disagreeing substring is a bug
    # somewhere upstream rather than something to store quietly
    schema = SpanSchema(classes=["PER"])
    with pytest.raises(SchemaError, match="offsets are authoritative"):
        schema.validate_value(Spans(values=[Span(label="PER", start=0, end=3, text="Alice")]))


def test_span_text_may_be_omitted():
    SpanSchema(classes=["PER"]).validate_value(
        Spans(values=[Span(label="PER", start=0, end=5)])
    )


def test_an_unknown_span_class_is_refused():
    with pytest.raises(SchemaError, match="ORG"):
        SpanSchema(classes=["PER"]).validate_value(
            Spans(values=[Span(label="ORG", start=0, end=3)])
        )


def test_spans_answer_the_indexing_contract():
    schema = SpanSchema(classes=["PER", "ORG"])
    value = Spans(
        values=[Span(label="PER", start=0, end=3), Span(label="ORG", start=5, end=8)]
    )
    assert schema.classes_asserted(value) == {"PER", "ORG"}


def test_a_document_with_no_spans_asserts_nothing():
    assert SpanSchema(classes=["PER"]).classes_asserted(Spans()) == set()


# ----------------------------------------------------------------------
# Boxes
# ----------------------------------------------------------------------


def test_a_box_round_trips():
    box = Box(label="car", x=0.1, y=0.2, width=0.3, height=0.4)
    assert Box.model_validate_json(box.model_dump_json()) == box


def test_boxes_are_fractions_not_percentages():
    # Label Studio speaks percentages; converting at the boundary is what
    # keeps a stored box meaningful without the original dimensions
    with pytest.raises(ValidationError, match="fractions of the image"):
        Box(label="car", x=50.0, y=50.0, width=10.0, height=10.0)


def test_a_box_outside_the_image_is_refused():
    with pytest.raises(ValidationError, match="fractions of the image"):
        Box(label="car", x=0.9, y=0.1, width=1.5, height=0.2)


def test_a_negative_extent_is_refused():
    with pytest.raises(ValidationError, match="Negative extent"):
        Box(label="car", x=0.1, y=0.1, width=-0.2, height=0.2)


def test_a_zero_area_box_is_allowed():
    # Degenerate but real: a click that never became a drag
    assert Box(label="car", x=0.5, y=0.5, width=0.0, height=0.0).width == 0.0


def test_rotation_defaults_to_none():
    assert Box(label="car", x=0.1, y=0.1, width=0.2, height=0.2).rotation == 0.0


def test_a_box_prediction_carries_confidences():
    prediction = BoxesPrediction(
        values=[Box(label="car", x=0.1, y=0.1, width=0.2, height=0.2)], confidences=[0.6]
    )
    assert isinstance(prediction, Boxes)
    assert prediction.confidences == [0.6]


def test_an_unknown_box_class_is_refused():
    with pytest.raises(SchemaError, match="lorry"):
        BBoxSchema(classes=["car"]).validate_value(
            Boxes(values=[Box(label="lorry", x=0.1, y=0.1, width=0.2, height=0.2)])
        )


def test_boxes_answer_the_indexing_contract():
    schema = BBoxSchema(classes=["car", "bike"])
    value = Boxes(
        values=[
            Box(label="car", x=0.1, y=0.1, width=0.2, height=0.2),
            Box(label="bike", x=0.5, y=0.5, width=0.1, height=0.1),
            Box(label="car", x=0.7, y=0.1, width=0.1, height=0.1),
        ]
    )
    assert schema.classes_asserted(value) == {"car", "bike"}


def test_an_image_with_no_boxes_asserts_nothing():
    # And is a real annotation: a human looked and there was nothing there
    assert BBoxSchema(classes=["car"]).classes_asserted(Boxes()) == set()


# ----------------------------------------------------------------------
# The unions
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"kind": "choices", "values": ["cat"]}, Choices),
        ({"kind": "spans", "values": [{"label": "PER", "start": 0, "end": 3}]}, Spans),
        (
            {
                "kind": "boxes",
                "values": [
                    {"label": "car", "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}
                ],
            },
            Boxes,
        ),
    ],
)
def test_a_value_recovers_its_type_from_json(payload, expected):
    # What lets a reader pull an annotation out of storage without being
    # told which task produced it
    assert isinstance(TypeAdapter(AnyValue).validate_python(payload), expected)


@pytest.mark.parametrize("task", ["classification", "span", "bbox"])
def test_a_schema_recovers_its_type_from_json(task):
    restored = TypeAdapter(AnySchema).validate_python({"task": task, "classes": ["a"]})
    assert restored.task == task


def test_an_unknown_kind_is_refused():
    with pytest.raises(ValidationError):
        TypeAdapter(AnyValue).validate_python({"kind": "polygons", "values": []})


# ----------------------------------------------------------------------
# Shared class-list rules
# ----------------------------------------------------------------------


@pytest.mark.parametrize("schema_cls", [SpanSchema, BBoxSchema])
def test_duplicate_classes_are_refused_for_every_task(schema_cls):
    with pytest.raises(ValidationError, match="Duplicate"):
        schema_cls(classes=["a", "b", "a"])


@pytest.mark.parametrize("schema_cls", [SpanSchema, BBoxSchema])
def test_empty_class_names_are_refused_for_every_task(schema_cls):
    with pytest.raises(ValidationError, match="cannot be empty"):
        schema_cls(classes=["a", " "])
