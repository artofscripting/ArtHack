#!/usr/bin/env python3
"""ART — ASCII dungeon-escape game.

Run from a terminal on Linux:

    ./.venv/bin/python main.py

"""
from __future__ import annotations

import argparse
import datetime
import random
import sys

from game import Game


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="ART — ASCII dungeon escape.")
    p.add_argument("--seed", type=int, default=None,
                   help="seed the procedural generator for repeatable layouts")
    p.add_argument("--start-bonus", action="store_true",
                   help="spawn a debug kit (weapon, haversack, gems, modules) and triple XP gain")
    p.add_argument("--daily", action="store_true",
                   help="play today's daily-seed challenge and record your best score")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    daily = args.daily
    if daily:
        # Everyone playing on the same date gets the same dungeon.
        random.seed(int(datetime.date.today().strftime("%Y%m%d")))
    elif args.seed is not None:
        random.seed(args.seed)

    if not sys.stdout.isatty():
        print("ART must be run in an interactive terminal.", file=sys.stderr)
        return 2

    Game(start_bonus=args.start_bonus, daily=daily).run()
    print("Farewell, Art.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
