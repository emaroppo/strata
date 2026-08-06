"""Baseline models shipped with auto-labeller.

A project selects one through ``[model] ref`` in ``project.toml``, or points
at its own ``model.py`` when it needs a bespoke architecture.
"""

from .classifier import MulticlassClassifier, MultiLabelClassifier, PresenceClassifier

__all__ = ["MulticlassClassifier", "MultiLabelClassifier", "PresenceClassifier"]
