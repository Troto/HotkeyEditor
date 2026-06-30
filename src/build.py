#!/usr/bin/python
"""Build every game's self-contained page and the shared launcher.

Discovers games/<slug>/game_module_generator.py, builds each into
site/<slug>/index.html, and writes the site/index.html launcher listing all of
them.  This is the all-games build; to (re)build a single game while iterating,
run that game's generator directly, e.g.:

    python3 games/aoe2/game_module_generator.py --build

Data regeneration (--regen) is per game and needs a game install, so it stays on
the individual generators.  Stdlib only (Python 3.7).
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
import page_assembler  # noqa: E402


if __name__ == '__main__':
    built = page_assembler.build_all(_ROOT)
    sys.exit(0 if built else 1)
