"""What an annotation is, independent of who produced or stores it.

Value types, schema descriptors, and the conversions between them. Shared by
every other package in the workspace, which is what makes the constraint
below load-bearing rather than tidiness.

**May import:** the standard library and pydantic. These are pydantic models
deliberately: the same definitions then serve storage (JSONB), the dataset
manifest, and modelling's request types, so a value has one description
rather than three that drift. It also means a change here is a wire-format
change, and wants to be treated as one.

**May not import:** anything doing I/O, any storage layer, any ML framework,
and — most easily forgotten — Label Studio. What Label Studio puts on the
wire is one annotation tool's format; it converts at the boundary, inside
``strata.labeller``, and never reaches the catalog.

The indexing contract lives here too: every schema answers *which classes
does this annotation assert*, which is what lets the catalog index
annotations it does not otherwise understand.

Empty until Phase 1 — see ``docs/roadmap.md``.
"""
