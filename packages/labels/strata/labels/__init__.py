"""What an annotation is, independent of who produced or stores it.

Value types, schema descriptors, the manifest, and the conversions between
them: the one package every other may import, so a value has one
description. A change here is a wire-format change.

**May import:** the standard library and pydantic.

**May not import:** anything doing I/O, any storage layer, any ML
framework, or Label Studio, whose format converts inside ``strata.labeller``.

Every schema answers which classes an annotation asserts (``docs/adr/0039``).
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
    "AnyPrediction",
    "AnySchema",
    "AnyValue",
    "BBoxSchema",
    "Box",
    "Boxes",
    "BoxesPrediction",
    "Choices",
    "ChoicesPrediction",
    "ClassificationSchema",
    "Manifest",
    "ManifestFormatError",
    "ManifestSample",
    "Prediction",
    "SchemaError",
    "Span",
    "SpanSchema",
    "Spans",
    "SpansPrediction",
    "Value",
    "feature_digest",
    "order_digest",
    "sides_from_string",
    "sides_string",
]
