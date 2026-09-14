# 34. A model is found by name, and its framework is an extra

**Status:** accepted

## The decision

A model is named by a short name that resolves through an entry point, or by a
`file.py:Class` reference for a model the project carries. Baselines are
registered by module, so a framework loads only when a model that needs it is
asked for. `available()` reads what is installed. A baseline named on an
install without its framework is refused with the name of the extra.

## Why a name

A request crosses a wire, and the backend decides what it can serve; a
capability list fetched earlier would be stale by the time a round is sent.
The file reference keeps the quick-experiment path, anchored at the project so
a run can be read back when its directory is gone (record 0005), and refused
over the wire because it is a path on the caller's machine (record 0007).

## Why the framework is an extra

Torch is gigabytes, and most of what the packages do never touches it: the
catalog, the labeller, the experiment runner and every test that does not train
run on a base install. A bespoke model never installs the baselines'
framework. The registry imports a module only when its name is asked for, and
the shared furniture the baselines grew in parallel lives outside the
package's `__init__` so the registry can import it on a base install.

## Consequences

- "What can this host serve" is answered from what is installed on the host,
  which is the only honest answer.
- The common case on a laptop is naming a baseline the laptop cannot run, so
  the error names the extra rather than a missing module.
