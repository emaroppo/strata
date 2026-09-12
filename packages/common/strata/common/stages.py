"""What a stage declares about itself.

A stage is a function taking a request and a context and returning a
record. This is the shape around it: a name a config can use, a version
recorded beside the spec hash, and what kind of thing it consumes and
produces, so a chain of stages can be checked before the first one runs.

The kinds are opaque strings here. What they name is each package's
business; this only has to be able to compare two of them.
"""

from collections.abc import Callable
from typing import Any, NamedTuple


class Stage(NamedTuple):
    """One named, versioned operation, and the kinds it links."""

    name: str
    #: Bumped when behaviour changes in a way that moves the result. Recorded
    #: beside the spec hash: a changed implementation under an unchanged spec
    #: is a different result.
    version: str
    #: What it needs to have been produced before it runs. Empty for a stage
    #: that starts from the catalog alone.
    consumes: tuple[str, ...]
    #: What it produces, for the next stage to consume.
    produces: str
    run: Callable[..., Any]


__all__ = ["Stage"]
