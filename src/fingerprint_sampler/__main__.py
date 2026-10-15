"""`python -m fingerprint_sampler` and the `fingerprint` console command."""

import sys

from fingerprint_sampler.cli import main as cli_main


def main() -> None:
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
