"""What a label set is: the task, its classes, and the rules over them.

A schema is stored data — it is what ``catalog.label_set`` holds — so it is a
model rather than a class hierarchy with behaviour bolted on. The behaviour
it does carry is pure: validating a value against the class list, and saying
which classes a value asserts.

An empty class list is allowed, on the grounds that a label set exists
before anyone has decided what is in it — but it validates nothing, so
every value is rejected until classes are declared. The labeller currently
infers a class list from what is in use when a project declares none
(``schema.classes or get_classes(...)`` in ``train.py``); that inference has
no equivalent here and goes away when the labeller moves onto label sets.

Deliberately absent: what the sample is made of. ``image_classification``
and ``text_classification`` were Label Studio template names; classifying a
photograph and classifying a document are the same task, and which one a
sample is belongs to the catalog.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .values import Choices


class SchemaError(ValueError):
    """A value that does not fit the schema it is annotated against."""


class ClassificationSchema(BaseModel):
    """Classes for a whole sample."""

    task: Literal["classification"] = "classification"
    #: Append-only by convention: a checkpoint maps output neurons to this
    #: list by position, so reordering invalidates every checkpoint silently.
    classes: list[str] = Field(default_factory=list)
    #: False for mutually exclusive classes.
    multiple: bool = True

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _classes_are_usable(self) -> "ClassificationSchema":
        if any(not c.strip() for c in self.classes):
            raise ValueError("Class names cannot be empty")
        duplicates = {c for c in self.classes if self.classes.count(c) > 1}
        if duplicates:
            raise ValueError(f"Duplicate class(es): {', '.join(sorted(duplicates))}")
        return self

    def validate_value(self, value: Choices) -> None:
        """Raise if ``value`` does not fit this schema.

        An empty value is valid and meaningful: a sample a human looked at
        and found nothing in is a real answer, not a missing one.
        """
        unknown = [c for c in value.values if c not in self.classes]
        if unknown:
            raise SchemaError(
                f"Class(es) not in this label set: {', '.join(sorted(unknown))} "
                f"(known: {', '.join(self.classes) or 'none'})"
            )
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

    def classes_asserted(self, value: Choices) -> set[str]:
        return set(value.values)

    # Ranking is deliberately not here. A prediction carries its
    # confidences; how to turn those into a review order — least-confident,
    # entropy, margin — is an active-learning strategy, and active learning
    # belongs to the labeller.


#: Every schema, discriminated on ``task``. One member today — adding boxes
#: or spans is one class and one entry here.
AnySchema = ClassificationSchema
