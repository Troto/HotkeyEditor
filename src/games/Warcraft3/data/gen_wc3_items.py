#!/usr/bin/env python3
"""Generate data/wc3_items.json: a disposition token for every Warcraft III item code.

Item *purchase* hotkeys (a shop's "Purchase X" buttons) exist in CustomKeys.txt as ordinary
`[code]` sections, but WC3 **templates every item with the same fields**, so a huge number of these
purchase sections are boilerplate the game never actually uses (duplicate/legacy rawcodes, items no
shop sells). The base game data has no shop->item ownership link for most items either (only the
Goblin Merchant carries a fixed `Sellitems=` list — everything else is placed per-map in the World
Editor; see games/Warcraft3/README.md). So we can't card these to a shop, but we CAN decide, from
Blizzard's `itemdata.slk` (+ the `*func.txt` profiles, all vendored under `slk data/`), whether a
purchase hotkey is ever reachable in a real match, and drop the ones that aren't.

An item's purchase hotkey is **used in a match** iff the item can appear at a shop or in the neutral
drop/marketplace pool:
    - it's in some shop's `Sellitems=` list (a fixed shop stocks it), OR
    - it has a `Buttonpos` (a fixed slot on a shop's command card), OR
    - `pickRandom == 1` (it's in the random creep-drop / Marketplace pool).
Signals we deliberately do NOT use: `droppable` is `1` for ~all items (a template default, not a
usage marker); `class` alone doesn't say if an item is used.

Disposition token per item:
    - "campaign"  -> `class == "Campaign"` (quest/campaign items — Shadow Orb Fragment, Wirt's Leg,
                     …). Kept visible but grouped into the editor's Campaign column, not melee.
    - "melee"     -> used in a match (per the test above), not campaign. Shown as "Neutral Items".
    - "hidden"    -> ruled out: not campaign, and no shop/pool ever offers it. A template/unused
                     purchase hotkey; the module drops it from the list (still round-trips on save).

Run from anywhere:  python3 games/Warcraft3/data/gen_wc3_items.py
Reads:  games/Warcraft3/data/slk data/itemdata.slk  +  slk data/*func.txt (Buttonpos / Sellitems)
Writes: games/Warcraft3/data/wc3_items.json
"""
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_HERE, 'slk data')
_ITEMDATA = os.path.join(_SRC_DIR, 'itemdata.slk')

# itemdata.slk columns we read (looked up by header name, not fixed index).
_WANT = ('itemID', 'class', 'pickRandom', 'sellable')

_CELL_X = re.compile(r';X(\d+)')
_CELL_Y = re.compile(r';Y(\d+)')
# a cell value is a quoted string (K"Permanent") or a bare number (K1 -- SLK stores ints/bools
# unquoted), so match both.
_CELL_K = re.compile(r';K"([^"]*)"|;K(-?\d+(?:\.\d+)?)')

_SECTION = re.compile(r'^\[(.*?)\]')
_BUTTONPOS = re.compile(r'^\s*Buttonpos\s*=\s*(-?\d+)\s*,\s*(-?\d+)', re.I)
_SELLITEMS = re.compile(r'^\s*Sellitems\s*=(.+)', re.I)


def parse_slk(path):
    """Parse an SLK into {row: {col: value}}.  Y is sticky (only the row's first cell repeats it),
    X is explicit on every cell."""
    rows = {}
    y = None
    with open(path, encoding='latin-1') as fh:
        for line in fh:
            if not line.startswith('C;'):
                continue
            ym = _CELL_Y.search(line)
            if ym:
                y = int(ym.group(1))
            xm = _CELL_X.search(line)
            km = _CELL_K.search(line)
            if xm and km and y is not None:
                rows.setdefault(y, {})[int(xm.group(1))] = km.group(1) if km.group(1) is not None else km.group(2)
    return rows


def scan_profiles():
    """Scan the `*func.txt` profiles for the two shop signals: item codes that have a `Buttonpos`
    (a fixed shop-card slot) and item codes named in any `Sellitems=` list (a fixed shop stocks
    them).  Returns (buttonpos_set, sellitems_set), lower-cased codes."""
    bpos, sells = set(), set()
    for name in sorted(os.listdir(_SRC_DIR)):
        if not name.lower().endswith('func.txt'):
            continue
        cur = None
        with open(os.path.join(_SRC_DIR, name), encoding='latin-1') as fh:
            for line in fh:
                line = line.rstrip('\r\n')
                sm = _SECTION.match(line)
                if sm:
                    cur = sm.group(1).lower()
                    continue
                bm = _BUTTONPOS.match(line)
                if bm and cur and int(bm.group(1)) >= 0 and int(bm.group(2)) >= 0:
                    bpos.add(cur)
                    continue
                lm = _SELLITEMS.match(line)
                if lm:
                    for code in lm.group(1).split(','):
                        code = code.strip().lower()
                        if code:
                            sells.add(code)
    return bpos, sells


def main():
    rows = parse_slk(_ITEMDATA)
    header = rows.get(1, {})
    col = {name: x for x, name in header.items() if name in _WANT}
    bpos, sells = scan_profiles()

    out = {}
    for y, row in rows.items():
        if y == 1:
            continue
        code = row.get(col.get('itemID'))
        if not code:
            continue
        code = code.lower()
        cls = row.get(col.get('class'), '')
        if cls == 'Campaign':
            out[code] = 'campaign'
            continue
        used = row.get(col.get('pickRandom'), '') == '1' or code in bpos or code in sells
        out[code] = 'melee' if used else 'hidden'

    dst = os.path.join(_HERE, 'wc3_items.json')
    with open(dst, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, separators=(',', ':'), sort_keys=True)
        fh.write('\n')
    from collections import Counter
    by = Counter(out.values())
    print('wrote %s: %d items (%s)'
          % (dst, len(out), ', '.join('%s=%d' % (k, by[k]) for k in sorted(by))))


if __name__ == '__main__':
    main()
