"""`python -m fingerprint_sampler` and the `fingerprint` console command."""

from __future__ import annotations

import sys


def main() -> None:
    from fingerprint_sampler.cli import main as cli_main

    sys.exit(cli_main())


if __name__ == "__main__":
    main()
