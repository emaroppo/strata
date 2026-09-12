# strata-prepare-video

Video into frames a catalog can hold, grouped so one video cannot straddle
a split. A plugin to `strata-catalog`, found through its entry points,
carrying OpenCV.

```bash
uv add strata-prepare-video
```

## What it adds

| entry point | name | what it does |
|---|---|---|
| `strata.preparers` | `video-frames` | `.mp4`, `.mov`, `.mkv` and the rest into `frames` |

Frames are written one directory per video, sampled every `every` frames
up to `max_frames`, as JPEG at `quality`. The prepared index declares one
group per video, which is what keeps consecutive near-duplicate frames on
one side of a split; the directory layout says the same thing for tools
that read only that.

Every frame is decoded in order and most are thrown away, rather than
seeking by frame number: a seek lands on the nearest keyframe, which
depends on the codec, and decoding in order is the only way the same
frames come out on a second run. Determinism is what keeps a re-prepared
corpus from re-checksumming into new samples.

## Tests

```bash
uv run pytest packages/prepare-video
```

Includes the catalog's `PreparerContract`.
