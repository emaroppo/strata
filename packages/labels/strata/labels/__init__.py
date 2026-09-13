"""What an annotation is, independent of who produced or stores it.

Value types, schema descriptors, the manifest, and the conversions between
them: the one package every other may import, so a value has one
description. A change here is a wire-format change.

**May import:** the standard library and pydantic.

**May not import:** anything doing I/O, any storage layer, any ML
framework, or Label Studio, whose format converts inside ``strata.labeller``.

Every schema answers *which classes does this annotation assert*, which is
what lets the catalog index annotations it does not otherwise understand.
Why the manifest lives here: ``docs/adr/0004``.
"""

from .manifest import (
    FILES_DIR,
    MANIFEST_FORMAT,
    MANIFEST_NAME,
    Manifest,
    ManifestFormatError,
    ManifestSample,
    feature_digest,
    order_digest,
    sides_from_string,
    sides_string,
)
from .schema import AnySchema, BBoxSchema, ClassificationSchema, SchemaError, SpanSchema
from .values import (
    AnyPrediction,
    AnyValue,
    Box,
    Boxes,
    BoxesPrediction,
    Choices,
    ChoicesPrediction,
    Prediction,
    Span,
    Spans,
    SpansPrediction,
    Value,
)

__all__ = [
    "FILES_DIR",
    "MANIFEST_FORMAT",
    "MANIFEST_NAME",
    "AnySchema",
    "AnyPrediction",
    "AnyValue",
    "BBoxSchema",
    "Box",
    "Boxes",
    "BoxesPrediction",
    "Choices",
    "ChoicesPrediction",
    "Manifest",
    "ManifestFormatError",
    "ManifestSample",
    "order_digest",
    "sides_from_string",
    "sides_string",
    "Prediction",
    "ClassificationSchema",
    "SchemaError",
    "Span",
    "SpanSchema",
    "Spans",
    "SpansPrediction",
    "Value",
    "feature_digest",
]
