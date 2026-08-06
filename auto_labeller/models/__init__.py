"""Baseline models shipped with auto-labeller.

A project selects one through ``[model] ref`` in ``project.toml``, or points
at its own ``model.py`` when it needs a bespoke architecture. Importing a
baseline pulls in its framework, so they are imported on demand.
"""

__all__ = [
    "MulticlassClassifier",
    "MultiLabelClassifier",
    "PresenceClassifier",
    "TextClassifier",
    "TextSpanTagger",
]


def __getattr__(name: str):
    if name in {"MulticlassClassifier", "MultiLabelClassifier", "PresenceClassifier"}:
        from . import classifier

        return getattr(classifier, name)
    if name in {"TextClassifier", "TextSpanTagger"}:
        from . import text_classifier

        return getattr(text_classifier, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
