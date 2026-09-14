"""Resolving a name through an entry-point group, on entries built by hand."""

from collections.abc import Mapping
from importlib.metadata import EntryPoint

import pytest

from strata.common.plugins import available, find, load

GROUP = "strata.test"


class Refused(Exception):
    pass


def _entry(name: str, value: str) -> EntryPoint:
    return EntryPoint(name, value, GROUP)


TWO = [_entry("ordered", "collections:OrderedDict"), _entry("chain", "collections:ChainMap")]


def test_available_reads_names_and_targets():
    assert available(TWO) == {
        "ordered": "collections:OrderedDict",
        "chain": "collections:ChainMap",
    }


def test_find_returns_the_one_entry_by_name():
    assert find(TWO, "chain", what="thing", error=Refused).value == "collections:ChainMap"


def test_an_unknown_name_lists_what_is_installed_and_the_hint():
    entries = [_entry("ordered", "collections:OrderedDict")]
    expected = r"No thing named 'nope'\. Installed here: ordered\. Try a path"
    with pytest.raises(Refused, match=expected):
        find(entries, "nope", what="thing", error=Refused, hint=" Try a path.")


def test_nothing_installed_says_none():
    with pytest.raises(Refused, match="Installed here: none"):
        find([], "nope", what="thing", error=Refused)


def test_a_name_registered_twice_is_refused_not_first_wins():
    entries = [_entry("dup", "collections:OrderedDict"), _entry("dup", "collections:ChainMap")]
    with pytest.raises(Refused, match="'dup' is registered more than once"):
        find(entries, "dup", what="thing", error=Refused)


def test_a_reserved_name_taken_by_a_plugin_says_so():
    entries = [_entry("image", "collections:OrderedDict"), _entry("image", "collections:ChainMap")]
    with pytest.raises(Refused, match="'image' is built in and cannot be replaced"):
        find(entries, "image", what="thing", error=Refused, reserved={"image"})


def test_load_checks_the_base_class():
    assert load(_entry("ordered", "collections:OrderedDict"), Mapping, error=Refused).__name__ == (
        "OrderedDict"
    )
    with pytest.raises(Refused, match=r"'deque' resolves to .* which is not a Mapping"):
        load(_entry("deque", "collections:deque"), Mapping, error=Refused)


def test_an_import_failure_is_not_this_layers_to_explain():
    with pytest.raises(ImportError):
        load(_entry("gone", "definitely_not_installed:Thing"), Mapping, error=Refused)
