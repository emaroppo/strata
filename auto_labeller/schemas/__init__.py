"""Label schemas: one per task type, selected by a project's template.

``[label_config] template`` in project.toml picks both the Label Studio
config and the schema that reads it. ``template = "custom"`` hands the
project's own XML to Label Studio verbatim and derives the schema by
parsing it, so a config tuned by hand stays authoritative.
"""

import re

from .base import LabelSchema, Prediction, Result, strip_volatile
from .bbox import BBoxSchema, Box, BoxOutput
from .classification import ChoiceOutput, ClassificationSchema

CUSTOM_TEMPLATE = "custom"

# template name -> schema class
TEMPLATES: dict[str, type[LabelSchema]] = {
    ClassificationSchema.type: ClassificationSchema,
    BBoxSchema.type: BBoxSchema,
}

# Label Studio control tag -> schema class, for reading a custom config
CONTROL_TAGS: dict[str, type[LabelSchema]] = {
    schema.control_tag: schema for schema in TEMPLATES.values()
}


class SchemaError(Exception):
    """Raised when a schema cannot be built from a project or a config."""


def available_templates() -> list[str]:
    return sorted([*TEMPLATES, CUSTOM_TEMPLATE])


def from_template(template: str, classes: list[str], **params) -> LabelSchema:
    """Build a schema from a template name and the project's parameters."""
    try:
        schema_cls = TEMPLATES[template]
    except KeyError:
        raise SchemaError(
            f"Unknown template '{template}' (available: {', '.join(available_templates())})"
        ) from None
    accepted = schema_cls.__init__.__code__.co_varnames
    unknown = [k for k in params if k not in accepted]
    if unknown:
        raise SchemaError(
            f"Template '{template}' takes no parameter(s): {', '.join(sorted(unknown))}"
        )
    return schema_cls(classes, **params)


def from_label_config(xml: str) -> LabelSchema:
    """Derive a schema by reading a labeling config.

    The config is authoritative for a custom project: control names and the
    class list come from the XML, because that is what annotations in
    Label Studio will actually reference.
    """
    for tag, schema_cls in CONTROL_TAGS.items():
        match = re.search(rf"<{tag}\b([^>]*)>", xml)
        if not match:
            continue
        attrs = match.group(1)
        from_name = _attr(attrs, "name") or "label"
        to_name = _attr(attrs, "toName") or "image"
        item = "Choice" if tag == "Choices" else "Label"
        classes = re.findall(rf"<{item}\s[^>]*value=\"([^\"]*)\"", xml)
        params: dict[str, str] = {"from_name": from_name, "to_name": to_name}
        if schema_cls is ClassificationSchema:
            params["choice"] = _attr(attrs, "choice") or "multiple"
        return schema_cls(classes, **params)

    known = ", ".join(sorted(CONTROL_TAGS))
    raise SchemaError(
        f"No supported labeling control in the config (looked for: {known}). "
        "Label Studio supports more than auto-labeller does; a schema for "
        "this control would have to be added."
    )


def _attr(attrs: str, name: str) -> str | None:
    match = re.search(rf'{name}="([^"]*)"', attrs)
    return match.group(1) if match else None


__all__ = [
    "BBoxSchema",
    "Box",
    "BoxOutput",
    "ChoiceOutput",
    "ClassificationSchema",
    "LabelSchema",
    "Prediction",
    "Result",
    "SchemaError",
    "available_templates",
    "from_label_config",
    "from_template",
    "strip_volatile",
]
