"""Video into frames, and the grouping that makes the split honest.

Needs OpenCV, which is the plugin's whole reason for being its own
distribution. The videos are generated in-process: a handful of flat
coloured frames is enough to assert which frames were taken, what they were
grouped as, and that a second run produces the same files.
"""

import pytest

cv2 = pytest.importorskip("cv2", reason="needs the video preparer's decoder")
np = pytest.importorskip("numpy")

from strata.catalog.types.prepared import PreparedIndex  # noqa: E402
from strata.catalog.types.preparer_conformance import PreparerContract  # noqa: E402
from strata.catalog.types.preparers import PreparerError, run  # noqa: E402
from strata.prepare_video.frames import VideoFramesPreparer  # noqa: E402

FPS = 10.0


def write_video(path, frames: int = 10, shade_from: int = 0):
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (32, 24)
    )
    if not writer.isOpened():  # pragma: no cover - depends on the build
        pytest.skip("this OpenCV cannot write mp4v")
    for i in range(frames):
        writer.write(np.full((24, 32, 3), (shade_from + i * 20) % 255, dtype=np.uint8))
    writer.release()
    return path


@pytest.fixture
def clip(tmp_path):
    return write_video(tmp_path / "clip.mp4", frames=10)


def test_one_frame_in_every_n_is_kept(clip, tmp_path):
    index = run(VideoFramesPreparer(every=5), [clip], tmp_path / "out")
    assert [e.metadata["frame_index"] for e in index.samples.values()] == [0, 5]


def test_every_frame_of_one_video_is_one_group(clip, tmp_path):
    """The reason this preparer exists.

    Consecutive frames are near-duplicates. A split putting some in train
    and the rest in validation scores a model on what it has memorised.
    """
    index = run(VideoFramesPreparer(every=2), [clip], tmp_path / "out")
    videos = {entry.metadata["video"] for entry in index.samples.values()}
    assert len(videos) == 1
    assert videos != {None}


def test_two_videos_are_two_groups(tmp_path):
    first = write_video(tmp_path / "one.mp4", frames=4)
    second = write_video(tmp_path / "two.mp4", frames=4, shade_from=100)
    index = run(VideoFramesPreparer(every=2), [first, second], tmp_path / "out")
    assert len({entry.metadata["video"] for entry in index.samples.values()}) == 2


def test_the_frames_are_admitted_by_the_frames_type(clip, tmp_path):
    from strata.catalog.types.sample_types import resolve

    out = tmp_path / "out"
    index = run(VideoFramesPreparer(every=5), [clip], out)
    frames = resolve("frames")()
    assert all(frames.allows(out / name) for name in index.samples)


def test_the_type_reads_the_group_off_the_index(clip, tmp_path):
    """What a directory layout could only imply, declared as a fact."""
    from strata.catalog.types.sample_types import resolve

    out = tmp_path / "out"
    index = run(VideoFramesPreparer(every=5), [clip], out)
    frames = resolve("frames")()
    name = next(iter(index.samples))
    assert frames.metadata_for(out / name, out)["video"] == index.samples[name].metadata["video"]


def test_a_frame_knows_where_in_the_video_it_was(clip, tmp_path):
    index = run(VideoFramesPreparer(every=5), [clip], tmp_path / "out")
    entry = list(index.samples.values())[1]
    assert entry.metadata["frame_index"] == 5
    assert entry.metadata["seconds"] == pytest.approx(5 / FPS)


def test_the_count_can_be_capped(clip, tmp_path):
    index = run(VideoFramesPreparer(every=1, max_frames=3), [clip], tmp_path / "out")
    assert len(index.samples) == 3


def test_a_second_run_writes_the_same_frames(clip, tmp_path):
    """Determinism is what keeps a re-prepared corpus from re-checksumming.

    Names carry the video's own checksum and the frame's index, so nothing
    depends on the order videos were converted in.
    """
    first = run(VideoFramesPreparer(every=5), [clip], tmp_path / "one")
    second = run(VideoFramesPreparer(every=5), [clip], tmp_path / "two")
    assert set(first.samples) == set(second.samples)
    for name in first.samples:
        assert (tmp_path / "one" / name).read_bytes() == (
            tmp_path / "two" / name
        ).read_bytes()


def test_a_file_that_will_not_open_is_reported(tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    with pytest.raises(PreparerError, match="could not open|no frames"):
        run(VideoFramesPreparer(), [broken], tmp_path / "out")


def test_a_stride_below_one_is_refused():
    with pytest.raises(PreparerError, match="at least 1"):
        VideoFramesPreparer(every=0)


def test_the_index_survives_being_written(clip, tmp_path):
    out = tmp_path / "out"
    index = run(VideoFramesPreparer(every=5), [clip], out)
    assert PreparedIndex.load(out).samples.keys() == index.samples.keys()


class TestVideoFramesConform(PreparerContract):
    @pytest.fixture
    def preparer(self):
        return VideoFramesPreparer(every=5)

    @pytest.fixture
    def source(self, tmp_path):
        return write_video(tmp_path / "clip.mp4", frames=10)
