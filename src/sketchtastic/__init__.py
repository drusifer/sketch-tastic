"""sketch-tastic: mergeable sketches of JSONL event streams.

Reduce each event to a stable fingerprint, and keep one entry per distinct
fingerprint — with counts, statistics and samples you choose — in a set that
grows across runs.
"""

from importlib.metadata import PackageNotFoundError, version

from sketchtastic.aggregators import Aggregate, Aggregator, Op
from sketchtastic.fingerprint_set import (
    Fingerprint,
    FingerprintSet,
    FingerprintSetError,
    ProfileMismatchError,
    fingerprint_id,
)
from sketchtastic.model import Field, Modifier, Path, Rule
from sketchtastic.profile import (
    Profile,
    ProfileError,
    check_profile,
    load_profile,
    parse_profile,
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
    "Fingerprint",
    "FingerprintSetError",
    "Modifier",
    "Profile",
    "ProfileError",
    "ProfileMismatchError",
    "Path",
    "Rule",
    "FingerprintSet",
    "__version__",
    "check_profile",
    "fingerprint_id",
    "load_profile",
    "parse_profile",
]
