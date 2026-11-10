#!/usr/bin/env python3
"""Tichu terminal entry point; rules live in the import-safe tichu package.

Original project by Johannes Knoerzer, January 2021.
"""
from tichu.cards import Card, Deck
from tichu.game import Player, Round, Match
from tichu.cli import main


if __name__ == '__main__':
    raise SystemExit(main())
