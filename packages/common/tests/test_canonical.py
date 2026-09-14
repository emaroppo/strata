"""The canonical form, and the one payload every implementation hashes.

``strata.common.contract.PAYLOAD`` is checked in once; the digest below was
computed by ``post-process``'s own implementation over it before that
package imported this one, and every package that hashes anything pins
the same digest in its tests. If this fails, the rules changed meaning:
bump ``CANONICAL_VERSION`` and recompute, and every consumer's pin fails
on upgrade, which is the point.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from strata.common.canonical import (
    CANONICAL_VERSION,
    canonical_json,
    content_hash,
    hash_file,
    short_hash,
    to_jsonable,
)
from strata.common.contract import PAYLOAD

CONTRACT_JSON = (
    '{"alpha":{"nested":{"x":true,"y":null},"when":"2026-09-12"},"big":9007199254740992,'
    '"count":7,"empty":[],"flag":false,"kind":"alpha","none":{},"pair":[1,"two"],'
    '"point":{"x":1,"y":2},"ratio":0.25,"stamp":"2026-09-12T13:45:00","text":"café — 日本",'
    '"tick":"2026-09-12T13:45:00.123456","zeta":[3,1,2]}'
)
CONTRACT_HASH = "ff7fdb1e6ac5180784e6665dc600bce4887a6a045e0e9c5a24c5b43104771556"


def test_the_contract_payload_hashes_as_pinned():
    assert CANONICAL_VERSION == 1
    assert canonical_json(PAYLOAD) == CONTRACT_JSON
    assert content_hash(PAYLOAD) == CONTRACT_HASH


def test_hash_file_reads_raw_bytes_and_counts_them(tmp_path):
    path = tmp_path / "release.bin"
    path.write_bytes(b"abc" * 1000)
    digest, size = hash_file(path, chunk_size=7)
    assert size == 3000
    assert digest == hash_file(path)[0]


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
    assert content_hash(PAYLOAD).startswith(short_hash(PAYLOAD))
    assert len(short_hash(PAYLOAD, 12)) == 12
    with pytest.raises(ValueError, match="collide"):
        short_hash(PAYLOAD, 4)
