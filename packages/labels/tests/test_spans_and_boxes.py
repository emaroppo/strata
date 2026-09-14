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
    span = Span(labels=["PER"], start=4, end=9, text="Alice")
    assert Span.model_validate_json(span.model_dump_json()) == span


def test_spans_are_sorted_into_reading_order():
    # So a stored annotation and a model's output compare equal when they
    # say the same thing
    spans = Spans(values=[Span(labels=["B"], start=10, end=12), Span(labels=["A"], start=0, end=3)])
    assert [s.label for s in spans.values] == ["A", "B"]


def test_two_span_sets_in_different_orders_are_equal():
    first = Spans(values=[Span(labels=["A"], start=0, end=3), Span(labels=["B"], start=5, end=7)])
    second = Spans(values=[Span(labels=["B"], start=5, end=7), Span(labels=["A"], start=0, end=3)])
    assert first == second


def test_a_backwards_range_is_refused():
    with pytest.raises(ValidationError, match="Not a range"):
        Span(labels=["PER"], start=9, end=4)


def test_a_negative_offset_is_refused():
    with pytest.raises(ValidationError, match="Not a range"):
        Span(labels=["PER"], start=-1, end=4)


def test_an_empty_span_is_allowed():
    # A zero-width range is a real thing to annotate: an insertion point
    assert Span(labels=["PER"], start=4, end=4).end == 4


def test_a_span_prediction_carries_confidences():
    prediction = SpansPrediction(values=[Span(labels=["PER"], start=0, end=3)], confidences=[0.7])
    assert isinstance(prediction, Spans)
    assert prediction.confidences == [0.7]


def test_confidences_follow_their_span_into_reading_order():
    prediction = SpansPrediction(
        values=[Span(labels=["B"], start=10, end=12), Span(labels=["A"], start=0, end=3)],
        confidences=[0.2, 0.9],
    )
    assert [s.label for s in prediction.values] == ["A", "B"]
    assert prediction.confidences == [0.9, 0.2]


def test_spans_are_ordered_when_parsed_from_json():
    parsed = SpansPrediction.model_validate(
        {
            "kind": "spans",
            "values": [
                {"labels": ["B"], "start": 10, "end": 12},
                {"labels": ["A"], "start": 0, "end": 3},
            ],
            "confidences": [0.2, 0.9],
        }
    )
    assert [s.label for s in parsed.values] == ["A", "B"]
    assert parsed.confidences == [0.9, 0.2]


def test_a_malformed_span_in_a_set_is_reported_by_field_validation():
    with pytest.raises(ValidationError, match="Not a range"):
        Spans.model_validate({"kind": "spans", "values": [{"labels": ["A"], "start": 5, "end": 1}]})


def test_span_text_must_match_its_offsets():
    # The offsets are authoritative, so a disagreeing substring is a bug
    # somewhere upstream rather than something to store quietly
    schema = SpanSchema(classes=["PER"])
    with pytest.raises(SchemaError, match="offsets are authoritative"):
        schema.validate_value(Spans(values=[Span(labels=["PER"], start=0, end=3, text="Alice")]))


def test_span_text_may_be_omitted():
    SpanSchema(classes=["PER"]).validate_value(Spans(values=[Span(labels=["PER"], start=0, end=5)]))


def test_an_unknown_span_class_is_refused():
    with pytest.raises(SchemaError, match="ORG"):
        SpanSchema(classes=["PER"]).validate_value(
            Spans(values=[Span(labels=["ORG"], start=0, end=3)])
        )


# ----------------------------------------------------------------------
# What a region may carry, and what two regions may do
# ----------------------------------------------------------------------


def test_a_span_written_with_one_label_no_longer_reads():
    # The single-label form was migrated in place (catalog and prediction
    # cache each have a migration for it); the reader does not accept it.
    with pytest.raises(ValidationError):
        Span.model_validate({"label": "name", "start": 0, "end": 4})


def test_a_region_with_no_labels_is_allowed():
    # A region sent without one is not an error; an empty string is not a
    # class name, so it carries none.
    assert Span.model_validate({"labels": [], "start": 0, "end": 4}).labels == []


def test_a_region_can_carry_two_labels():
    schema = SpanSchema(classes=["name", "place"], multi_label=True)
    value = Spans(values=[Span(labels=["name", "place"], start=0, end=4)])
    schema.validate_value(value)
    assert schema.classes_asserted(value) == {"name", "place"}


def test_a_second_label_is_refused_where_it_was_not_declared():
    schema = SpanSchema(classes=["name", "place"])
    with pytest.raises(SchemaError, match="single-label"):
        schema.validate_value(Spans(values=[Span(labels=["name", "place"], start=0, end=4)]))


def test_an_unknown_class_is_found_on_any_label():
    schema = SpanSchema(classes=["name"], multi_label=True)
    with pytest.raises(SchemaError, match="place"):
        schema.validate_value(Spans(values=[Span(labels=["name", "place"], start=0, end=4)]))


def test_overlapping_regions_are_refused_where_they_were_not_declared():
    schema = SpanSchema(classes=["name", "place"])
    with pytest.raises(SchemaError, match="overlap"):
        schema.validate_value(
            Spans(
                values=[
                    Span(labels=["name"], start=0, end=10),
                    Span(labels=["place"], start=5, end=15),
                ]
            )
        )


def test_a_nested_region_is_an_overlap_too():
    schema = SpanSchema(classes=["name", "place"])
    with pytest.raises(SchemaError, match="overlap"):
        schema.validate_value(
            Spans(
                values=[
                    Span(labels=["name"], start=0, end=20),
                    Span(labels=["place"], start=5, end=10),
                ]
            )
        )


def test_two_regions_at_one_offset_are_told_what_they_should_be():
    # The mistake this catches is building a multi-label region as two
    # spans, and the message has to say so or the fix looks like a flag
    schema = SpanSchema(classes=["name", "place"], multi_label=True)
    with pytest.raises(SchemaError, match="one span with both"):
        schema.validate_value(
            Spans(
                values=[
                    Span(labels=["name"], start=0, end=4),
                    Span(labels=["place"], start=0, end=4),
                ]
            )
        )


def test_overlaps_are_allowed_where_they_were_declared():
    schema = SpanSchema(classes=["name", "place"], overlapping=True)
    schema.validate_value(
        Spans(
            values=[
                Span(labels=["name"], start=0, end=10),
                Span(labels=["place"], start=5, end=15),
            ]
        )
    )


def test_touching_regions_do_not_overlap():
    # End-exclusive offsets: 0..4 and 4..8 share no character
    SpanSchema(classes=["name", "place"]).validate_value(
        Spans(
            values=[
                Span(labels=["name"], start=0, end=4),
                Span(labels=["place"], start=4, end=8),
            ]
        )
    )


def test_the_two_declarations_are_separate_questions():
    # A job can want shared regions without partial overlap, or the other
    # way round, and one flag could not say either
    both_off = SpanSchema(classes=["a"])
    assert (both_off.multi_label, both_off.overlapping) == (False, False)
    assert SpanSchema(classes=["a"], multi_label=True).overlapping is False
    assert SpanSchema(classes=["a"], overlapping=True).multi_label is False


def test_spans_answer_the_indexing_contract():
    schema = SpanSchema(classes=["PER", "ORG"])
    value = Spans(
        values=[Span(labels=["PER"], start=0, end=3), Span(labels=["ORG"], start=5, end=8)]
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
        ({"kind": "spans", "values": [{"labels": ["PER"], "start": 0, "end": 3}]}, Spans),
        (
            {
                "kind": "boxes",
                "values": [{"label": "car", "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}],
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
