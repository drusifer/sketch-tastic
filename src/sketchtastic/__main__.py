"""`python -m sketchtastic` and the `sketchtastic` / `skt` console commands."""

import sys

from sketchtastic.cli import main as cli_main


def main() -> None:
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
