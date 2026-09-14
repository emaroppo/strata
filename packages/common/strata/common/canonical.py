"""Canonical JSON, and the hash taken over it.

Every spec the orchestrator runs is identified by the hash of its canonical
form, and the argument for JSON is not that it is declarative: it is that
it **hashes**. A spec that cannot be canonically serialised cannot be an
identity, and a changed spec that hashes the same silently reuses what the
old one produced.

Canonical means: sorted keys, no incidental whitespace, defaults already
materialised by the caller, and a refusal for anything whose serialisation
is not single-valued. Two specs that mean the same thing hash the same;
two that differ anywhere do not.

The one implementation: ``strata-post-process`` and ``strata-feature-store``
import it rather than re-declare it (``docs/adr/0017``). The payload every
consumer pins the digest of is ``strata.common.contract``.
"""

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

#: Bumped if the canonical form itself changes meaning, which would make
#: every previously recorded hash incomparable rather than merely different.
CANONICAL_VERSION = 1


def to_jsonable(payload: Any) -> Any:
    """``payload`` reduced to what :func:`json.dumps` accepts, refusing the rest.

    The refusals are the point. A set has no order, so two runs would
    serialise it two ways and hash differently while meaning the same
    thing. A timezone-aware datetime means two clocks are in play and the
    hash would record which. A NaN has no JSON form every reader agrees on.
    """
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"object keys must be strings for a stable ordering, got {type(key).__name__}"
                )
            out[key] = to_jsonable(value)
        return out
    if isinstance(payload, (list, tuple)):
        return [to_jsonable(item) for item in payload]
    if isinstance(payload, (set, frozenset)):
        raise TypeError(
            "a set has no order, so it cannot be canonicalised. Sort it into a list at the "
            "point it is built, so the order is a decision rather than an accident."
        )
    if isinstance(payload, Enum):
        return to_jsonable(payload.value)
    if isinstance(payload, datetime):
        if payload.tzinfo is not None:
            raise ValueError(
                f"{payload!r} is timezone-aware. Everything here is naive UTC; an aware value "
                "means two clocks are in play and the hash would silently record which."
            )
        return payload.isoformat()
    if isinstance(payload, date):
        return payload.isoformat()
    if isinstance(payload, bool) or payload is None or isinstance(payload, (str, int)):
        return payload
    if isinstance(payload, float):
        if payload != payload or payload in (float("inf"), float("-inf")):
            raise ValueError(f"{payload!r} has no JSON representation")
        return payload
    if is_dataclass(payload) and not isinstance(payload, type):
        return to_jsonable(asdict(payload))
    if hasattr(payload, "model_dump"):
        # A pydantic model, without this package depending on pydantic:
        # dumped in python mode so dates stay dates and are handled above.
        return to_jsonable(payload.model_dump(mode="python"))
    raise TypeError(f"no canonical form for {type(payload).__name__}")


def canonical_json(payload: Any) -> str:
    """The one textual form of ``payload`` that this system hashes."""
    return json.dumps(
        to_jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(payload: Any) -> bytes:
    """:func:`canonical_json` as UTF-8, which is what actually gets hashed."""
    return canonical_json(payload).encode("utf-8")


def content_hash(payload: Any) -> str:
    """The full sha256 hex of ``payload``'s canonical form."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def short_hash(payload: Any, length: int = 16) -> str:
    """A truncated :func:`content_hash`, for a directory name a person reads.

    Refuses to go below eight characters: a short hash is for readability,
    and one short enough to collide is not a saving.
    """
    if length < 8:
        raise ValueError(f"a {length}-character hash is short enough to collide; use 8 or more")
    return content_hash(payload)[:length]


def hash_file(path, chunk_size: int = 1 << 20) -> tuple[str, int]:
    """The digest of a file's bytes, and how many there were.

    The one hash over raw bytes rather than a canonical form: a release is
    its bytes, and what those bytes mean is not this function's business.
    """
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


__all__ = [
    "CANONICAL_VERSION",
    "canonical_bytes",
    "canonical_json",
    "content_hash",
    "hash_file",
    "short_hash",
    "to_jsonable",
]
