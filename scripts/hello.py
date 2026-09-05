#!/usr/bin/env python3
"""Minimal BotBox example script."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BotBox hello example")
    parser.add_argument("-n", "--name", default="Bot Box", help="who to greet")
    args = parser.parse_args(argv)
    print(f"hello from BotBox, {args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
