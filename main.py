#!/usr/bin/env python3
"""ART — ASCII dungeon-escape game.

Run from a terminal on Linux:

    ./.venv/bin/python main.py

"""
from __future__ import annotations

import argparse
import random
import sys

from game import Game


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="ART — ASCII dungeon escape.")
    p.add_argument("--seed", type=int, default=None,
                   help="seed the procedural generator for repeatable layouts")
    p.add_argument("--start-bonus", action="store_true",
                   help="spawn a debug kit (weapon, haversack, gems, modules) and triple XP gain")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.seed is not None:
        random.seed(args.seed)

    if not sys.stdout.isatty():
        print("ART must be run in an interactive terminal.", file=sys.stderr)
        return 2

    Game(start_bonus=args.start_bonus).run()
    print("Farewell, Art.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
