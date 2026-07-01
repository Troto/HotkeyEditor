#!/usr/bin/env python3
"""Build wc3_names.json (code -> display name) from Warcraft III's own game data.

The game files are the **source of truth for every command name**.  Each object table
(`*data.slk`) is paired with a set of `strings/*.txt` files that carry the localized display
text keyed by the same 4-char rawcode.  A hotkey triggers an *action*, so we prefer the `Tip=`
(the button's action label -- "Build Barracks", "Train Footman", "Research Control Magic") over
the `Name=` (the bare object -- "Barracks", "Footman").  Priority for a code:

  1. strings `[CODE]` block, `Tip=` line   -- the button/action label.  Preferred.
  2. strings `[CODE]` block, `Name=` line  -- the object's display name; fills codes with no `Tip=`.
  3. `*data.slk` `comment(s)` column        -- an internal DEV label; fills codes with neither.

Multi-level values (upgrades/leveled abilities) are stored in the game files as an *unquoted*
comma list of per-tier labels (`Upgrade to Iron Forged Swords,Upgrade to Steel...`), whereas a
name that genuinely contains a comma is *quoted* (`"Storm, Earth, And Fire"`).  We keep the
level-1 label via `first_level()` (respects the quoting).  Leveled `Tip=`s also carry inline
color markup + a level suffix (`Holy Light - [|cffffcc00Level 1|r]`); `clean_tip()` strips both
so a hero ability reads as just "Holy Light".

Emits a flat {lower-cased code: name} map.  The WC3 module (`module.js`) uses it as the source of
truth for every record's display name (unit-card commands, common commands, globals, and the
"Miscellaneous" tail), falling back to the jcfields dataset only when the game files name a code
with neither a strings entry nor an SLK comment.

The derived `wc3_names.json` is committed; the raw SLK/txt tables are NOT vendored.  To regenerate,
copy them out of a Warcraft III install (the `.slk`/`*Func.txt` object tables + their `strings/`
counterparts) into a directory and point this script at it.

Usage:  python3 gen_wc3_names.py [path/to/slk-dir]
  (default slk-dir = "../slk data files" relative to this script; strings in its "strings/" subdir)

Stdlib only (Python 3.7).  See SOURCE.md for provenance.
"""
import glob
import json
import os
import re
import sys

# WC3 inline color codes (|cAARRGGBB ... |r) and a trailing " - [Level N]" decoration that leveled
# button tips carry (`Holy Light - [|cffffcc00Level 1|r]`).  Stripped so a tip reads as a plain name.
_COLOR_RE = re.compile(r'\|c[0-9a-fA-F]{8}|\|[rn]')
_LEVEL_RE = re.compile(r'\s*-\s*\[?\s*Level\s+\d+\s*\]?\s*$', re.I)


def clean_tip(v):
    return _LEVEL_RE.sub('', _COLOR_RE.sub('', v)).strip()

_HERE = os.path.dirname(os.path.abspath(__file__))
SLK_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, os.pardir, 'slk data files')
STRINGS_DIR = os.path.join(SLK_DIR, 'strings')

# (file, id-column-name, name-column-name); first match wins across files, in this order
TABLES = [
    ('itemdata.slk', 'itemID', 'comment'),
    ('abilitydata.slk', 'alias', 'comments'),
    ('unitdata.slk', 'unitID', 'comment(s)'),
    ('upgradedata.slk', 'upgradeid', 'comments'),
]


def first_level(v):
    """Level-1 name of a game-data value.

    A quoted value is a single name that may contain commas (`"Storm, Earth, And Fire"`); an
    unquoted value is a per-tier comma list (`Improved...,Advanced...`) -- keep the first tier.
    """
    v = v.strip()
    if v[:1] == '"':
        j = v.find('"', 1)
        return (v[1:j] if j != -1 else v[1:]).strip()
    i = v.find(',')
    return (v if i == -1 else v[:i]).strip()


def parse_strings(path):
    """Return (names, tips): {lower code: level-1 name} for the `Name=`/`Tip=` lines of a
    `[CODE]` strings file (first value per section wins within the file)."""
    names, tips = {}, {}
    code = None
    with open(path, encoding='utf-8-sig') as f:      # utf-8-sig strips the BOM
        for line in f:
            line = line.rstrip()                     # drop trailing \n\r plus any stray tab/space
            if line[:1] == '[' and line[-1:] == ']':  # some headers are `[hfoo]\t` -> rstrip first
                code = line[1:-1].lower()
            elif not code:
                continue
            elif line[:5] == 'Name=' and code not in names:
                val = first_level(line[5:])
                if val:
                    names[code] = val
            elif line[:4] == 'Tip=' and code not in tips:
                val = clean_tip(first_level(line[4:]))
                if val:
                    tips[code] = val
    return names, tips


def parse_slk(path):
    """Yield one dict per data row (keyed by the header row's column names)."""
    rows = {}
    cx = cy = None
    with open(path, encoding='latin-1') as f:
        for line in f:
            if not line or line[0] != 'C':
                continue
            x = y = val = None
            for fld in line.rstrip('\n').rstrip('\r').split(';')[1:]:
                if not fld:
                    continue
                tag, rest = fld[0], fld[1:]
                if tag == 'X':
                    x = int(rest)
                elif tag == 'Y':
                    y = int(rest)
                elif tag == 'K':
                    val = rest
            if x is not None:
                cx = x
            if y is not None:
                cy = y
            if val is None:
                continue
            if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
                val = val[1:-1]
            rows.setdefault(cy, {})[cx] = val
    if not rows:
        return []
    header = rows[min(rows)]
    return [{header.get(x, x): v for x, v in rows[y].items()}
            for y in sorted(rows) if y != min(rows)]


def main():
    # Layers, lowest priority first; each fills only codes still unnamed above it.
    from_name = {}   # strings Name=  (object display names; fills codes with no Tip=)
    from_tip = {}    # strings Tip=   (button action label -- preferred)
    for path in sorted(glob.glob(os.path.join(STRINGS_DIR, '*.txt'))):
        names, tips = parse_strings(path)
        for k, v in names.items():
            from_name.setdefault(k, v)     # first strings file to name a code wins
        for k, v in tips.items():
            from_tip.setdefault(k, v)
        print('strings/%-28s %4d Name  %4d Tip' % (os.path.basename(path), len(names), len(tips)))

    from_slk = {}    # SLK dev-comment labels (last-resort fill)
    for fname, idcol, namecol in TABLES:
        n = 0
        for rec in parse_slk(os.path.join(SLK_DIR, fname)):
            code, name = rec.get(idcol), rec.get(namecol)
            if code and name:
                from_slk.setdefault(str(code).lower(), name)
                n += 1
        print('%-22s %4d rows' % (fname, n))

    names = dict(from_slk)   # base layer (dev comments)
    names.update(from_name)  # Name beats SLK comment
    names.update(from_tip)   # Tip (the action label) is the source of truth

    out = os.path.join(_HERE, 'wc3_names.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(names, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    print('wrote %s (%d codes: %d Tip / %d Name-only / %d SLK-only, %d bytes)' % (
        out, len(names), len(from_tip),
        len([k for k in from_name if k not in from_tip]),
        len([k for k in from_slk if k not in from_tip and k not in from_name]),
        os.path.getsize(out)))


if __name__ == '__main__':
    main()
