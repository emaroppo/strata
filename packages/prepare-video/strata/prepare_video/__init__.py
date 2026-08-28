"""Video into frames.

The hole this fills was visible from the other side for a while: the
``frames`` sample type has always known that frames of one video must not
straddle a train/val split, and nothing in the tree made frames. The
scripts that once did were deleted with the rest of the pre-catalog
tooling, so a corpus already extracted still ingests — one directory per
video is exactly what the type expects — and a new video cannot be turned
into one at all.

Grouping is declared here rather than left to that directory layout. Both
work; a converter saying which video a frame came from is a fact, where a
directory is a convention two pieces of code have to agree about.
"""

from .frames import VideoFramesPreparer

__all__ = ["VideoFramesPreparer"]
