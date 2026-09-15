"""The payload every implementation of the canonical form hashes.

One payload, checked in once, that exercises everything the rules have an
opinion on: key order, nesting, list order, every scalar, a date and two
datetimes (one on the second, one below it), an enum, a dataclass and an
empty container. Each package that hashes anything pins the digest of
this payload in its own tests. See ``docs/adr/0017``.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class Kind(Enum):
    A = "alpha"


@dataclass
class Point:
    x: int
    y: int


PAYLOAD = {
    "zeta": [3, 1, 2],
    "alpha": {"nested": {"y": None, "x": True}, "when": date(2026, 9, 12)},
    # Naive on purpose: the canonical form refuses an aware one. docs/adr/0017
    "stamp": datetime(2026, 9, 12, 13, 45, 0),  # noqa: DTZ001
    "tick": datetime(2026, 9, 12, 13, 45, 0, 123456),  # noqa: DTZ001
    "ratio": 0.25,
    "count": 7,
    "big": 2**53,
    "text": "café — 日本",
    "kind": Kind.A,
    "point": Point(1, 2),
    "pair": (1, "two"),
    "empty": [],
    "none": {},
    "flag": False,
}

__all__ = ["PAYLOAD"]
