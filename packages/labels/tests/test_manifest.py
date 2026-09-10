"""The manifest, and the digest the prediction cache keys on."""

from strata.labels import feature_digest


def test_the_empty_digest_is_empty():
    """A project with no features reads exactly as it did before there were any."""
    assert feature_digest({}) == ""
    assert feature_digest(None) == ""
    assert feature_digest({"a": 1}) != ""


def test_the_digest_does_not_depend_on_key_order():
    assert feature_digest({"a": 1, "b": 2}) == feature_digest({"b": 2, "a": 1})
