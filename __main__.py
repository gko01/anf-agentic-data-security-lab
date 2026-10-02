"""JSON stdin/stdout interface. No path supplied by a request is opened."""

import argparse
from datetime import date
import json
import sys

from .engine import PolicyEngine
from .providers import MockClassificationProvider


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline metadata-only policy demo")
    parser.add_argument("--baseline-demo", action="store_true",
                        help="Replay using 2026-10-02 as the evaluation date (not live authorization)")
    args = parser.parse_args()

    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate JSON key")
            obj[key] = value
        return obj

    try:
        raw = sys.stdin.read(16385)
        payload = json.loads(raw, object_pairs_hook=unique_object) if len(raw) <= 16384 else None
    except (ValueError, UnicodeError):
        payload = None
    engine = PolicyEngine(MockClassificationProvider(),
                          today=date(2026, 10, 2) if args.baseline_demo else None)
    decision = engine.evaluate(payload)
    print(json.dumps(decision.to_dict(), sort_keys=True))
    return 0 if decision.decision == "ALLOW" else 1


if __name__ == "__main__":
    sys.exit(main())
