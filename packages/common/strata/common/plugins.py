"""Resolving a name through an entry-point group.

Three groups use this — sample types, preparers, models — and each had
written the same lookup: find the entries with that name, refuse a name
registered twice rather than take whichever loaded first, check that what
loaded is the kind of thing asked for, and say what *is* installed when
nothing matches.

It takes the entries rather than the group, so a consumer keeps the one
seam its tests already patch: an ``entries()`` returning what is installed.
"""

from collections.abc import Collection, Iterable
from importlib.metadata import EntryPoint


def available(entries: Iterable[EntryPoint]) -> dict[str, str]:
    """Registered names, and what each resolves to.

    Read from what is installed rather than a list someone maintains,
    which is the only honest answer to "what can this do".
    """
    return {entry.name: entry.value for entry in entries}


def find(
    entries: Iterable[EntryPoint],
    name: str,
    *,
    what: str,
    error: type[Exception],
    reserved: Collection[str] = (),
    hint: str = "",
) -> EntryPoint:
    """The one entry ``name`` refers to, not yet loaded.

    ``what`` names the kind of thing for the message ("preparer"), and
    ``hint`` is appended when nothing matches, for a group with another
    way to name things. A name in ``reserved`` belongs to the package
    owning the group, and a plugin registering it is refused rather than
    resolved by install order: it would change behaviour and nothing would
    report it.
    """
    entries = list(entries)
    matches = [entry for entry in entries if entry.name == name]
    if not matches:
        known = ", ".join(sorted(available(entries))) or "none"
        raise error(f"No {what} named {name!r}. Installed here: {known}.{hint}")
    if len(matches) > 1:
        owners = ", ".join(_owner(entry) for entry in matches)
        detail = (
            f"{name!r} is built in and cannot be replaced"
            if name in reserved
            else f"{name!r} is registered more than once"
        )
        raise error(f"{detail} (from: {owners}).")
    return matches[0]


def load(entry: EntryPoint, base: type, *, error: type[Exception]) -> type:
    """What the entry names, checked to be a subclass of ``base``.

    An import failure propagates as it is: what to say about one depends on
    the group, and a caller with something to add wraps it.
    """
    loaded = entry.load()
    if not (isinstance(loaded, type) and issubclass(loaded, base)):
        raise error(f"{entry.name!r} resolves to {loaded!r}, which is not a {base.__name__}.")
    return loaded


def _owner(entry: EntryPoint) -> str:
    return getattr(getattr(entry, "dist", None), "name", "?")


__all__ = ["available", "find", "load"]
