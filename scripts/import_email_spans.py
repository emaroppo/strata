"""Turn a corpus of pre-parsed email JSON into a labelling project.

    uv run python scripts/import_email_spans.py prepare \
        corpus.json --project projects/my-emails
    uv run auto-labeller ingest -p my-emails
    uv run python scripts/import_email_spans.py seed --project projects/my-emails

Two phases with the tool's own ``ingest`` between them, rather than one
script that does everything. ``ingest`` is where sample types, collections,
grouping and content addressing are decided, and a script reaching around it
would be a second implementation of the thing most worth having only one of.

**prepare** writes one ``.txt`` per message under the project's data root and
a sidecar recording the spans that came with it, keyed by the file it wrote.

**seed** reads that sidecar back, resolves each file to the sample ``ingest``
created for it, and lands a stratified subset as annotations.

Three things about the source data, established by measuring it rather than
assuming:

*The spans are candidates, not labels.* Every message carries
a validation flag set to false, and the classes are regex-shaped
(a handful of pattern-matched types) plus what looks
like an off-the-shelf model (``PER``, ``ORG``, ``LOC``). They are seeded so
that a reviewer has something to correct, never as ground truth, which is why
they land under a source of their own.

*Offsets are into ``body``, and they are sound.* All but 18 spans
satisfy ``body[start:end] == text`` exactly. The rest point past the end of
the body they belong to and are dropped, because a span that does not slice
to its own text is not a fact about this document.

*Nothing overlaps.* Which is what lets BIO tagging represent the whole corpus
without a nesting scheme.
"""

import argparse
import json
import random
import re
import sys
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

SIDECAR = "spans.json"

#: Messages longer than this are not imported at all. The figure is the
#: character equivalent of ~1024 tokens (chars-per-token is p50 3.98 over
#: this corpus), chosen because the encoder's window is 512 and a document
#: many times that is mostly automated bulk mail here.
#:
#: A cap on what enters the catalog is a compromise and worth naming as one:
#: it lets a model's limits decide what the durable asset contains, which is
#: the relationship the architecture puts the other way round. Accepted for a
#: first pass over a corpus whose labels are known to be poor; the source
#: JSON is retained, so raising it is a re-run rather than a loss.
DEFAULT_MAX_CHARS = 4000


def _safe_name(file_path: str, index: int) -> str:
    """A filename that survives the round trip and stays traceable.

    Derived from the source path so a sample can be tied back to the message
    it came from by looking at it, with the index guaranteeing uniqueness
    where two mailboxes hold a file of the same name.
    """
    stem = re.sub(r"[^A-Za-z0-9]+", "_", file_path).strip("_")[-80:]
    return f"{index:06d}_{stem or 'message'}.txt"


def prepare(source: Path, data_dir: Path, max_chars: int) -> dict:
    messages = json.loads(source.read_text())
    data_dir.mkdir(parents=True, exist_ok=True)

    spans_by_file: dict[str, list] = {}
    meta_by_file: dict[str, dict] = {}
    counts = Counter()

    for index, record in enumerate(messages):
        for message in record.get("messages", []):
            body = message.get("body") or ""
            if not body.strip():
                counts["empty"] += 1
                continue
            if len(body) > max_chars:
                counts["oversized"] += 1
                continue

            name = _safe_name(record.get("file_path", ""), index)
            (data_dir / name).write_text(body, encoding="utf-8")

            spans = []
            for label, items in ((message.get("entities") or {}).get("manual") or {}).items():
                for item in items or []:
                    if not (isinstance(item, list) and len(item) == 3):
                        counts["malformed"] += 1
                        continue
                    text, start, end = item
                    # The span has to slice to its own text or it is not
                    # about this document. Eighteen in the corpus do not.
                    if not isinstance(start, int) or not isinstance(end, int):
                        counts["dropped"] += 1
                        continue
                    if start < 0 or end > len(body) or start >= end:
                        counts["dropped"] += 1
                        continue
                    if body[start:end] != text:
                        counts["dropped"] += 1
                        continue
                    spans.append([label, start, end, text])
                    counts[f"span:{label}"] += 1

            spans_by_file[name] = sorted(spans, key=lambda s: (s[1], s[2]))
            headers = message.get("headers") or {}
            meta_by_file[name] = {
                # The join key that keeps raw .eml ingestion possible later:
                # re-importing the same corpus in another format produces
                # different bytes and therefore different samples, and this
                # is what would carry the review work across.
                "message_id": headers.get("Message-ID") or headers.get("Message-Id") or "",
                "subject": headers.get("Subject") or "",
                "from": headers.get("From") or "",
                "date": headers.get("Date") or "",
                "source_id": (message.get("_id") or {}).get("$oid", ""),
                "is_html": bool(message.get("is_html")),
            }
            counts["written"] += 1

    return {"spans": spans_by_file, "metadata": meta_by_file, "counts": dict(counts)}


def choose_seed(spans_by_file: dict[str, list], size: int, per_class: int, rng) -> list[str]:
    """A seed that contains every class, then fills out randomly.

    Purely random selection does not work here. The corpus is extremely
    skewed — one corpus measured here carried 136,203 ``URL`` spans against
    2,362 ``ORG`` — so a few hundred messages drawn at random may hold
    almost no ``ORG``. A
    model that never saw a class is confidently silent about it, and
    uncertainty sampling then never surfaces it either: the queue is ranked
    by a score with nothing behind it.

    The random remainder matters as much as the stratified core. Validation
    membership is assigned from whatever is labelled, so a seed that is
    *only* stratified yields a validation set with the same distortion, and
    the first number would flatter itself.
    """
    by_class: dict[str, list[str]] = defaultdict(list)
    for name, spans in spans_by_file.items():
        for label, *_ in spans:
            by_class[label].append(name)

    chosen: list[str] = []
    seen: set[str] = set()
    for label in sorted(by_class, key=lambda c: len(by_class[c])):
        pool = [n for n in by_class[label] if n not in seen]
        rng.shuffle(pool)
        for name in pool[:per_class]:
            chosen.append(name)
            seen.add(name)

    remainder = [n for n in spans_by_file if n not in seen]
    rng.shuffle(remainder)
    chosen.extend(remainder[: max(0, size - len(chosen))])
    return chosen


def _load(project_dir: Path, config_path: Path):
    from strata.labeller.config import Settings
    from strata.labeller.project import Project

    return Project.load(project_dir), Settings.load(config_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="Write .txt files and the span sidecar")
    p.add_argument("source", type=Path, help="One corpus JSON file")
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)

    s = sub.add_parser("seed", help="Land a stratified subset as annotations")
    s.add_argument("--project", type=Path, required=True)
    s.add_argument("--config", type=Path, default=Path("config.toml"))
    s.add_argument("--size", type=int, default=400, help="Messages in the seed")
    s.add_argument("--per-class", type=int, default=25, help="Minimum per class")
    s.add_argument("--random-seed", type=int, default=0)
    s.add_argument("--apply", action="store_true", help="Write; otherwise report only")

    args = parser.parse_args(argv)

    if args.command == "prepare":
        return _cmd_prepare(args)
    return _cmd_seed(args)


def _cmd_prepare(args) -> int:
    toml_path = args.project / "project.toml"
    if not toml_path.exists():
        print(f"No project.toml under {args.project}", file=sys.stderr)
        return 1
    data_root = tomllib.loads(toml_path.read_text()).get("data", {}).get("root", "data/raw")
    data_dir = args.project / data_root

    result = prepare(args.source, data_dir, args.max_chars)
    (args.project / SIDECAR).write_text(json.dumps(result))

    counts = result["counts"]
    print(f"Wrote {counts.get('written', 0):,} document(s) to {data_dir}")
    # Reported rather than silent: a corpus that arrives quietly smaller than
    # the file it came from is the failure this whole tree keeps guarding.
    print(f"  skipped {counts.get('oversized', 0):,} over {args.max_chars:,} characters")
    print(f"  skipped {counts.get('empty', 0):,} with an empty body")
    print(f"  dropped {counts.get('dropped', 0):,} span(s) that did not slice to their own text")
    for key in sorted(k for k in counts if k.startswith("span:")):
        print(f"    {key.removeprefix('span:'):11} {counts[key]:,}")
    print(f"\nNext: uv run auto-labeller ingest -p {args.project.name}")
    return 0


def _cmd_seed(args) -> int:
    from strata.catalog.blobs import checksum_of

    sidecar = args.project / SIDECAR
    if not sidecar.exists():
        print(f"No {SIDECAR} under {args.project}; run 'prepare' first.", file=sys.stderr)
        return 1
    payload = json.loads(sidecar.read_text())
    spans_by_file = payload["spans"]

    project, settings = _load(args.project, args.config)
    rng = random.Random(args.random_seed)
    chosen = choose_seed(spans_by_file, args.size, args.per_class, rng)

    histogram = Counter()
    for name in chosen:
        for label, *_ in spans_by_file[name]:
            histogram[label] += 1
    print(f"Seed of {len(chosen):,} message(s), carrying:")
    for label, n in histogram.most_common():
        print(f"    {label:11} {n:,}")

    if not args.apply:
        print("\nReport only. Pass --apply to write.")
        return 0

    from strata.labeller.cli import _catalog_for

    catalog, _root = _catalog_for(settings, args.config, name=project.catalog.name)
    label_set_id, _schema = catalog.label_set(project.label_set_name)

    from strata.labels import Span, Spans

    data_dir = project.data_dir
    items, missing = [], 0
    for name in chosen:
        path = data_dir / name
        if not path.exists():
            missing += 1
            continue
        row = catalog.by_checksum(checksum_of(path))
        if row is None:
            missing += 1
            continue
        items.append(
            (
                row.id,
                Spans(
                    values=[
                        Span(label=label, start=start, end=end, text=text)
                        for label, start, end, text in spans_by_file[name]
                    ]
                ),
            )
        )

    # Not "human": nobody has looked at these. The distinction is the only
    # thing separating a reviewed label from a regex's guess, and export
    # overwrites it with "human" the moment someone submits the task.
    annotated, _skipped = catalog.annotate_many(label_set_id, items, source="import")
    print(f"\nSeeded {annotated:,} annotation(s) as source='import'")
    if missing:
        print(f"  {missing:,} chosen file(s) were not in the catalog — run ingest first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
