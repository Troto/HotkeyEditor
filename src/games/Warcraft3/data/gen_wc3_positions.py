#!/usr/bin/env python3
"""Generate data/positions.json: WC3 command-card grid slots for each command code.

Warcraft III lays every command out on a 4-wide x 3-tall command card.  The slot of a
button is *not* in the data SLKs (that field's `slk` source is "Profile"); it lives in the
game's profile text files -- the `*func.txt` under data/slk data/ -- as INI sections:

    [Hfoo]
    Buttonpos=0,0            ; active button  (col X 0-3, row Y 0-2)
    Researchbuttonpos=3,2    ; research/learn button (upgrades, hero learn "+")
    Unbuttonpos=1,0          ; the off-state of a two-state toggle

We fold X,Y into a single row-major slot (`slot = Y*4 + X`, top-left = 0), matching the AoE2
positions.json convention, and emit three code->slot maps (active / research / unbutton) so the
module's GAME.slot can pick the right one per record channel.  Keyed by lower-cased 4-char code
(the game matches codes case-insensitively).

Run from anywhere:  python3 games/Warcraft3/data/gen_wc3_positions.py
Reads:  games/Warcraft3/data/slk data/*func.txt
Writes: games/Warcraft3/data/positions.json
"""
import json
import os
import re

CARD_COLS = 4  # WC3 command card is 4 columns x 3 rows

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_HERE, 'slk data')

SECTION_RE = re.compile(r'^\[([^\]]+)\]\s*$')
POS_RE = re.compile(r'^([A-Za-z]*[Bb]utton[Pp]os)\s*=\s*(-?\d+)\s*,\s*(-?\d+)')

# which position field feeds which of our three maps
FIELD_MAP = {
    'buttonpos': 'b',           # active command button
    'researchbuttonpos': 'r',   # research / hero-learn button
    'unbuttonpos': 'u',         # off-state of a two-state toggle
}


def slot_of(x, y):
    """Row-major slot on the 4x3 card, or None for an off-card (negative) position."""
    if x < 0 or y < 0:
        return None
    return y * CARD_COLS + x


def parse_file(path, out):
    """Merge one profile txt file's [code] Buttonpos values into `out` (first file wins)."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        code = None
        for raw in fh:
            line = raw.rstrip('\r\n')
            m = SECTION_RE.match(line)
            if m:
                code = m.group(1).strip().lower()
                continue
            if not code:
                continue
            pm = POS_RE.match(line.strip())
            if not pm:
                continue
            which = FIELD_MAP.get(pm.group(1).lower())
            if not which:
                continue
            slot = slot_of(int(pm.group(2)), int(pm.group(3)))
            if slot is None:
                continue
            out[which].setdefault(code, slot)   # first definition wins (see file order below)


def main():
    out = {'b': {}, 'r': {}, 'u': {}}
    # Load the per-race / common / item profiles before the broad neutral + campaign sets, so a
    # code defined in several files keeps its melee-race position (first-wins).  Campaign last:
    # it re-skins some melee codes for cinematics and we prefer the ladder layout.
    names = sorted(os.listdir(_SRC_DIR))
    def rank(n):
        n = n.lower()
        if n.startswith('campaign'):
            return 2
        if n.startswith('neutral'):
            return 1
        return 0
    for name in sorted(names, key=lambda n: (rank(n), n)):
        if not name.lower().endswith('func.txt'):
            continue
        parse_file(os.path.join(_SRC_DIR, name), out)

    # Drop the empty maps' redundancy: a code whose research/unbutton slot equals its active slot
    # adds nothing (GAME.slot falls back to 'b'), so keep only distinct entries small.
    for k in ('r', 'u'):
        out[k] = {c: s for c, s in out[k].items() if out['b'].get(c) != s}

    dst = os.path.join(_HERE, 'positions.json')
    with open(dst, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, separators=(',', ':'), sort_keys=True)
        fh.write('\n')
    print('wrote %s: %d active, %d research, %d unbutton slots'
          % (dst, len(out['b']), len(out['r']), len(out['u'])))


if __name__ == '__main__':
    main()
