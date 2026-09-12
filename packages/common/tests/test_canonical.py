"""The canonical form, and the contract it shares with the sister tools.

The first test pins a digest computed by ``post-process``'s own
implementation over the same payload. It is what keeps the three
re-declarations one contract: if this fails, either this module or theirs
has changed meaning, and the shared hashes are no longer comparable.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum

import pytest

from strata.common.canonical import (
    CANONICAL_VERSION,
    canonical_json,
    content_hash,
    short_hash,
    to_jsonable,
)


class Kind(Enum):
    A = "alpha"


#: Hashed by post-process 0.1.0's ``content_hash`` on 2026-09-12, at its
#: CANONICAL_VERSION 1. Recomputed there, not here, when either side changes.
CONTRACT_PAYLOAD = {
    "zeta": [3, 1, 2],
    "alpha": {"nested": {"y": None, "x": True}, "when": date(2026, 9, 12)},
    "stamp": datetime(2026, 9, 12, 13, 45, 0),
    "ratio": 0.25,
    "count": 7,
    "text": "café — 日本",
    "kind": Kind.A,
    "empty": [],
    "flag": False,
}
CONTRACT_JSON = (
    '{"alpha":{"nested":{"x":true,"y":null},"when":"2026-09-12"},"count":7,"empty":[],'
    '"flag":false,"kind":"alpha","ratio":0.25,"stamp":"2026-09-12T13:45:00",'
    '"text":"café — 日本","zeta":[3,1,2]}'
)
CONTRACT_HASH = "49e5ba7a67fcf11d95c8a03725984300ed0acf74f648f095740b2c4199ad6c9f"


def test_it_agrees_with_post_process():
    assert CANONICAL_VERSION == 1
    assert canonical_json(CONTRACT_PAYLOAD) == CONTRACT_JSON
    assert content_hash(CONTRACT_PAYLOAD) == CONTRACT_HASH


def test_key_order_and_whitespace_do_not_change_the_hash():
    a = {"b": 1, "a": {"y": [1, 2], "x": "s"}}
    b = {"a": {"x": "s", "y": [1, 2]}, "b": 1}
    assert content_hash(a) == content_hash(b)


def test_list_order_does_change_the_hash():
    assert content_hash({"k": [1, 2]}) != content_hash({"k": [2, 1]})


def test_a_dataclass_and_a_model_reduce_to_their_fields():
    @dataclass
    class Point:
        x: int
        y: int

    class Model:
        def model_dump(self, mode="python"):
            return {"x": 1, "y": 2}

    assert to_jsonable(Point(1, 2)) == {"x": 1, "y": 2}
    assert content_hash(Point(1, 2)) == content_hash(Model())


def test_a_set_is_refused():
    with pytest.raises(TypeError, match="no order"):
        canonical_json({"k": {1, 2}})


def test_a_non_string_key_is_refused():
    with pytest.raises(TypeError, match="keys must be strings"):
        canonical_json({1: "a"})


def test_an_aware_datetime_is_refused():
    with pytest.raises(ValueError, match="timezone-aware"):
        canonical_json({"at": datetime(2026, 9, 12, tzinfo=UTC)})


def test_nan_and_infinity_are_refused():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="no JSON representation"):
            canonical_json({"v": value})


def test_something_unknown_is_refused_not_stringified():
    with pytest.raises(TypeError, match="no canonical form for object"):
        canonical_json({"v": object()})


def test_short_hash_is_a_prefix_and_refuses_to_be_tiny():
    assert content_hash(CONTRACT_PAYLOAD).startswith(short_hash(CONTRACT_PAYLOAD))
    assert len(short_hash(CONTRACT_PAYLOAD, 12)) == 12
    with pytest.raises(ValueError, match="collide"):
        short_hash(CONTRACT_PAYLOAD, 4)
