"""sketch-tastic: mergeable sketches of JSONL event streams.

Reduce each event to a skit — a stable ID for one shape of event — and keep one
entry per skit, with counts, statistics and samples you choose, in a sketch that
grows across runs.
"""

from importlib.metadata import PackageNotFoundError, version

from sketchtastic.aggregators import Aggregate, Aggregator, Op
from sketchtastic.model import Field, Modifier, Path, Rule
from sketchtastic.profile import (
    Profile,
    ProfileError,
    check_profile,
    load_profile,
    parse_profile,
)
from sketchtastic.sketch import (
    ProfileMismatchError,
    Sketch,
    SketchError,
    Skit,
    skit_id,
)

try:
    __version__ = version("sketch-tastic")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0+unknown"

__all__ = [
    "Aggregate",
    "Aggregator",
    "Op",
    "Field",
    "Skit",
    "SketchError",
    "Modifier",
    "Profile",
    "ProfileError",
    "ProfileMismatchError",
    "Path",
    "Rule",
    "Sketch",
    "__version__",
    "check_profile",
    "skit_id",
    "load_profile",
    "parse_profile",
]
