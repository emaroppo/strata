"""What a label set is: the task, its classes, and the rules over them.

A schema is stored data — it is what ``catalog.label_set`` holds — so it is a
model rather than a class hierarchy with behaviour bolted on. The behaviour
it does carry is pure: validating a value against the class list, and saying
which classes a value asserts.

An empty class list is allowed and validates nothing. The label set is
authoritative: a project's file seeds its classes once. What the sample is
made of is deliberately absent; that is the catalog's. See
``docs/adr/0014``.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from .values import Boxes, Choices, Spans, Value


class SchemaError(ValueError):
    """A value that does not fit the schema it is annotated against."""


def _shared_class_validator():
    """The class-list rules every task type shares."""

    def check(self):
        if any(not c.strip() for c in self.classes):
            raise ValueError("Class names cannot be empty")
        duplicates = {c for c in self.classes if self.classes.count(c) > 1}
        if duplicates:
            raise ValueError(f"Duplicate class(es): {', '.join(sorted(duplicates))}")
        return self

    return model_validator(mode="after")(check)


def _expect[V: Value](kind: type[V], value: Value, task: str) -> V:
    """``value`` as the type a ``task`` label set holds, or a refusal that names both."""
    if not isinstance(value, kind):
        raise SchemaError(
            f"a {task} label set holds {kind.__name__}, not {type(value).__name__}"
        )
    return value


def _refuse_unknown_classes(known: list[str], used) -> None:
    unknown = sorted({c for c in used if c and c not in known})
    if unknown:
        raise SchemaError(
            f"Class(es) not in this label set: {', '.join(unknown)} "
            f"(known: {', '.join(known) or 'none'})"
        )


class ClassificationSchema(BaseModel):
    """Classes for a whole sample."""

    task: Literal["classification"] = "classification"
    #: Append-only by convention: a checkpoint maps output neurons to this
    #: list by position, so reordering invalidates every checkpoint silently.
    classes: list[str] = Field(default_factory=list)
    #: False for mutually exclusive classes.
    multiple: bool = True

    model_config = {"frozen": True}

    _classes_are_usable = _shared_class_validator()

    def validate_value(self, value: Value) -> None:
        """Raise if ``value`` does not fit this schema.

        An empty value is valid and meaningful: a sample a human looked at
        and found nothing in is a real answer, not a missing one.
        """
        value = _expect(Choices, value, self.task)
        _refuse_unknown_classes(self.classes, value.values)
        if not self.multiple and len(value.values) > 1:
            raise SchemaError(
                f"This label set is single-choice, got {len(value.values)}: "
                f"{', '.join(value.values)}"
            )
        duplicates = {c for c in value.values if value.values.count(c) > 1}
        if duplicates:
            raise SchemaError(f"Repeated class(es): {', '.join(sorted(duplicates))}")

    # -- the indexing contract -----------------------------------------
    #
    # The one question the catalog asks of a schema it does not otherwise
    # understand. Answering it is what makes "every sample labelled X" a
    # join rather than a scan, and a new task type becomes queryable by
    # implementing this and nothing else.

    def classes_asserted(self, value: Value) -> set[str]:
        value = _expect(Choices, value, self.task)
        return set(value.values)

    # Ranking is deliberately not here. A prediction carries its
    # confidences; how to turn those into a review order — least-confident,
    # entropy, margin — is an active-learning strategy, and active learning
    # belongs to the labeller.


class SpanSchema(BaseModel):
    """Labelled character ranges inside a document.

    ``multi_label`` and ``overlapping`` are separate questions about shape,
    both false by default, declared rather than inferred so a model can
    refuse before a round. See ``docs/adr/0014``.
    """

    task: Literal["span"] = "span"
    classes: list[str] = Field(default_factory=list)
    #: May one region carry more than one label?
    multi_label: bool = False
    #: May two regions intersect — nested, crossing or coincident?
    overlapping: bool = False

    model_config = {"frozen": True}

    _classes_are_usable = _shared_class_validator()

    def validate_value(self, value: Value) -> None:
        value = _expect(Spans, value, self.task)
        _refuse_unknown_classes(
            self.classes, (label for s in value.values for label in s.labels)
        )
        for span in value.values:
            if span.text and len(span.text) != span.end - span.start:
                raise SchemaError(
                    f"Span text is {len(span.text)} characters but the range "
                    f"{span.start}..{span.end} covers {span.end - span.start}; "
                    f"the offsets are authoritative, so one of them is wrong"
                )
            if not self.multi_label and len(span.labels) > 1:
                raise SchemaError(
                    f"The region {span.start}..{span.end} carries "
                    f"{len(span.labels)} labels ({', '.join(span.labels)}) and "
                    f"this label set is single-label. Set multi_label if that "
                    f"is what the job is."
                )
        if not self.overlapping:
            self._refuse_overlaps(value)

    def _refuse_overlaps(self, value: Spans) -> None:
        """No two regions may intersect.

        A sweep, since values arrive in reading order — but sorted again
        rather than assumed, because being wrong here means letting through
        exactly what this refuses.
        """
        spans = sorted(value.values, key=lambda s: (s.start, s.end))
        for earlier, later in zip(spans, spans[1:]):
            if later.start >= earlier.end:
                continue
            if (later.start, later.end) == (earlier.start, earlier.end):
                # Worth its own message: this is what a multi-label region
                # looks like when it has been built as two spans, and the
                # fix is one span with two labels rather than a flag.
                raise SchemaError(
                    f"Two regions share the offsets {earlier.start}..{earlier.end} "
                    f"({earlier.label} and {later.label}). A region carrying two "
                    f"labels is one span with both, not two spans."
                )
            raise SchemaError(
                f"The regions {earlier.start}..{earlier.end} and "
                f"{later.start}..{later.end} overlap, and this label set is "
                f"non-overlapping. Set overlapping if that is what the job is."
            )

    def classes_asserted(self, value: Value) -> set[str]:
        value = _expect(Spans, value, self.task)
        return {label for s in value.values for label in s.labels if label}


class BBoxSchema(BaseModel):
    """Labelled rectangles over an image."""

    task: Literal["bbox"] = "bbox"
    classes: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    _classes_are_usable = _shared_class_validator()

    def validate_value(self, value: Value) -> None:
        value = _expect(Boxes, value, self.task)
        _refuse_unknown_classes(self.classes, (b.label for b in value.values))

    def classes_asserted(self, value: Value) -> set[str]:
        value = _expect(Boxes, value, self.task)
        return {b.label for b in value.values if b.label}


#: Every schema, discriminated on ``task``.
AnySchema = Annotated[
    ClassificationSchema | SpanSchema | BBoxSchema, Field(discriminator="task")
]
