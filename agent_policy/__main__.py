"""Command-line entry point for the offline baseline demonstration."""

import argparse
import json
import sys
from datetime import date
from typing import Sequence

from .engine import PolicyEngine
from .providers import BaselineJsonProvider


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline Agent Policy Engine baseline demo.")
    parser.add_argument(
        "--baseline-demo",
        action="store_true",
        required=True,
        help="evaluate one JSON request from stdin using mock UI baseline metadata",
    )
    parser.parse_args(argv)

    engine = PolicyEngine()
    provider = BaselineJsonProvider()
    try:
        request_value = json.load(sys.stdin)
        exit_code = 0
    except (json.JSONDecodeError, UnicodeDecodeError):
        request_value = None
        exit_code = 2

    decision = engine.evaluate(request_value, provider)
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
