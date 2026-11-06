"""`python -m audial`: the same command line as `audial`."""

import sys

from audial.cli.commands import cli

if __name__ == "__main__":
    sys.exit(cli())
