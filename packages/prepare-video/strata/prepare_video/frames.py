"""Extracting frames, and declaring which video they came from.

**The grouping is the point.** Consecutive frames are near-duplicates, so a
split putting some of a video in train and the rest in validation scores a
model on what it has already memorised — which reads as a very good model.
The type has always known this; what it could only *infer*, from a
directory layout both sides had to agree about, is now declared as a fact
by the thing that actually knows: one group per video, in the prepared
index. Frames are still written one directory per video, so the corpus
stays browsable and a project prepared by something else still works.

**Every frame is decoded, and most are thrown away.** Seeking by frame
number is faster and lies: with inter-frame compression a seek lands on the
nearest keyframe, and which frame that is depends on the codec and the
encoder that produced the file. Decoding in order is the only way this
returns the same frames on a second run, and determinism is what keeps a
re-prepared corpus from re-checksumming into new samples.
"""

from pathlib import Path
from typing import ClassVar, Iterable

from strata.catalog import checksum_of
from strata.catalog.types.preparers import Prepared, Preparer, PreparerError

#: Container formats to admit. Not a claim about codecs: what OpenCV can
#: decode depends on how it was built, and a file it cannot read is
#: reported rather than skipped.
CONTAINERS = frozenset({"mp4", "mov", "mkv", "avi", "webm", "m4v"})

#: Enough of the video's own checksum to name its directory uniquely while
#: leaving the stem readable in front of it.
DIGEST_CHARS = 12


class VideoFramesPreparer(Preparer):
    """One video into one directory of frames."""

    name: ClassVar[str] = "video-frames"
    produces: ClassVar[str] = "frames"
    sources: ClassVar[frozenset[str]] = CONTAINERS

    def __init__(self, every: int = 30, max_frames: int | None = None, quality: int = 95):
        """``every`` frames, at most ``max_frames`` of them.

        One in thirty is about one a second on ordinary footage, and a
        second apart is roughly where consecutive frames stop being the
        same picture. Both are declared rather than clever: what a corpus
        needs depends on what is in it, and a default that guessed would be
        wrong quietly.
        """
        if every < 1:
            raise PreparerError(f"every must be at least 1, got {every}")
        self.every = every
        self.max_frames = max_frames
        self.quality = quality

    def prepare(self, source: Path, out_dir: Path) -> Iterable[Prepared]:
        import cv2

        source = Path(source)
        video = str(source)
        capture = cv2.VideoCapture(video)
        if not capture.isOpened():
            raise PreparerError(
                f"OpenCV could not open {source.name}. What it can decode "
                f"depends on how it was built, so this is a fact about the "
                f"install rather than about the file."
            )

        # The video's own checksum, so its frames keep their names
        group = f"{source.stem[-60:]}-{checksum_of(source)[:DIGEST_CHARS]}"
        directory = Path(out_dir) / group
        directory.mkdir(parents=True, exist_ok=True)
        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0

        index = kept = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if index % self.every == 0:
                    path = directory / f"{index:06d}.jpg"
                    if not cv2.imwrite(
                        str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
                    ):
                        raise PreparerError(f"Could not write {path}")
                    yield Prepared(
                        path=path,
                        metadata={
                            "source_file": source.name,
                            "frame_index": index,
                            # Null rather than a wrong number: a container
                            # that does not report a frame rate cannot be
                            # turned into a time by guessing one.
                            "seconds": round(index / fps, 3) if fps > 0 else None,
                            # Which video, as a fact rather than a directory
                            # layout: what a project names as its group_by
                            "video": group,
                        },
                    )
                    kept += 1
                    if self.max_frames is not None and kept >= self.max_frames:
                        break
                index += 1
        finally:
            capture.release()

        if kept == 0:
            raise PreparerError(
                f"{source.name} yielded no frames. It opened, so this is an "
                f"empty or unreadable stream rather than a missing decoder."
            )
