"""fingerprint-sampler: fingerprint and sample JSONL event streams.

Reduce each event to a stable fingerprint, and keep one entry per distinct
fingerprint — with counts, statistics and samples you choose — in a set that
grows across runs.
"""

from importlib.metadata import PackageNotFoundError, version

from fingerprint_sampler.aggregators import AggregateEntry, make_entry
from fingerprint_sampler.profile import (
    Profile,
    ProfileError,
    check_profile,
    load_profile,
    parse_profile,
)
from fingerprint_sampler.tokenizer import MaskEntry, Modifier, tokenize
from fingerprint_sampler.warehouse import (
    FingerprintRecord,
    FingerprintSetError,
    ProfileMismatchError,
    Warehouse,
    fingerprint_id,
)

try:
    __version__ = version("fingerprint-sampler")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0+unknown"

__all__ = [
    "AggregateEntry",
    "FingerprintRecord",
    "FingerprintSetError",
    "MaskEntry",
    "Modifier",
    "Profile",
    "ProfileError",
    "ProfileMismatchError",
    "Warehouse",
    "__version__",
    "check_profile",
    "fingerprint_id",
    "load_profile",
    "make_entry",
    "parse_profile",
    "tokenize",
]
