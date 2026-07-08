#!/usr/bin/env python3
"""Generate data/wc3_misc.json: mark Warcraft III unit codes whose build/train hotkey is dead.

Just as WC3 templates every *item* with the same purchase fields (see gen_wc3_items.py), it
templates every *unit* -- including buildings -- with a build/train command button: a `Buttonpos`
and a `[code]` section in CustomKeys.txt carrying a Hotkey.  For most units that hotkey is a real
command (the button a worker's build menu / a production building shows).  But many units' hotkey is
boilerplate the game never uses in a match, so it just clutters the editor's Miscellaneous group:
    - a family of neutral buildings -- Mercenary Camps (one rawcode per tileset), Dragon Roosts,
      Goblin Laboratory/Merchant/Shipyard, Tavern -- is only ever *placed in the World Editor*; and
    - every unit that only ever appears via an *ability* -- summoned / morphed / hired (Doom Guard,
      Clockwerk Goblin, the Destroyer form, Spirit Bear, …) -- is created by that ability, whose OWN
      hotkey is what a player presses; the summoned unit's train button is never shown or pressed.

So a unit's build/train/summon hotkey is **used in a match only if a command-card button produces
it** -- i.e. the unit is in some unit's `Builds=` / `Trains=` / `Sellunits=` / `Sellitems=` list
(from the `*unitfunc.txt` profiles).  Any unit that is *not producible* has a dead hotkey and is
tagged "unbuilt"; the module drops those from the list (they still round-trip byte-exact on save,
like the hidden item templates in gen_wc3_items.py).  (Being referenced by an ability -- summoned --
does NOT rescue it: that only means the unit appears, not that its train button is ever clicked.)

Run from anywhere:  python3 games/Warcraft3/data/gen_wc3_misc.py
Reads:  games/Warcraft3/data/slk data/unitdata.slk + abilitydata.slk + *unitfunc.txt
Writes: games/Warcraft3/data/wc3_misc.json
"""
import glob
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_HERE, 'slk data')

_SECTION = re.compile(r'^\[(.*?)\]')
_PRODUCE = ('Builds', 'Trains', 'Sellunits', 'Sellitems')


def parse_slk(path):
    """Parse an SLK into {row: {col: value}}.  Y is sticky (only the row's first cell repeats it),
    X is explicit on every cell."""
    rows = {}
    y = None
    with open(path, encoding='latin-1') as fh:
        for line in fh:
            if not line.startswith('C;'):
                continue
            ym = re.search(r';Y(\d+)', line)
            if ym:
                y = int(ym.group(1))
            xm = re.search(r';X(\d+)', line)
            km = re.search(r';K"([^"]*)"|;K(-?\d+(?:\.\d+)?)', line)
            if xm and km and y is not None:
                rows.setdefault(y, {})[int(xm.group(1))] = km.group(1) if km.group(1) is not None else km.group(2)
    return rows


def unit_codes():
    """The set of all unit rawcodes (lower-cased) from unitdata.slk."""
    rows = parse_slk(os.path.join(_SRC_DIR, 'unitdata.slk'))
    col = {name: x for x, name in rows.get(1, {}).items()}
    idc = col['unitID']
    out = set()
    for y, row in rows.items():
        if y != 1 and row.get(idc):
            out.add(str(row[idc]).lower())
    return out


def producible_codes(shown):
    """Unit codes offered by a **shown** builder / production building / shop, from the `*unitfunc.txt`
    Builds / Trains / Sellunits / Sellitems lists.  The producer must itself be browsable (`shown`):
    a unit produced only by an unshown (e.g. campaign-only) unit has no reachable produce button in the
    editor, so its own hotkey is just as dead as a summoned unit's -- e.g. Summon Doom Guard `nbal` /
    Fel Stalker `nfel` are trained only by campaign Dreadlord variants, while the melee versions come
    from the summon ability."""
    out = set()
    for name in sorted(os.listdir(_SRC_DIR)):
        if not name.lower().endswith('unitfunc.txt'):
            continue
        cur = None
        with open(os.path.join(_SRC_DIR, name), encoding='latin-1') as fh:
            for line in fh:
                line = line.rstrip('\r\n')
                m = _SECTION.match(line)
                if m:
                    cur = m.group(1).lower()
                    continue
                if cur not in shown:                         # only a browsable producer counts
                    continue
                for key in _PRODUCE:
                    if line.startswith(key + '='):
                        for code in line[len(key) + 1:].split(','):
                            code = code.strip().lower()
                            if code and code != '_':
                                out.add(code)
    return out


def ability_referenced(units):
    """Unit codes referenced as data by any ability in abilitydata.slk (summon / transform / hire
    targets).  Any 4-char cell value that is a known unit code counts -- over-including keeps a
    genuinely-spawned unit visible (the safe direction)."""
    rows = parse_slk(os.path.join(_SRC_DIR, 'abilitydata.slk'))
    out = set()
    for y, row in rows.items():
        if y == 1:
            continue
        for v in row.values():
            for part in re.split(r'[,\s]+', str(v).lower()):
                if len(part) == 4 and part in units:
                    out.add(part)
    return out


def load_shown():
    """The browsable-unit allowlist (wc3.json `shown`), lower-cased."""
    data = json.load(open(os.path.join(_HERE, 'wc3.json'), encoding='utf-8'))
    return {c.lower() for c in (data.get('shown') or [])}


def main():
    units = unit_codes()
    producible = producible_codes(load_shown())
    dead = sorted(u for u in units if u not in producible)
    referenced = ability_referenced(units)             # for the report only (how many dead are summons)
    summoned = sum(1 for u in dead if u in referenced)

    out = {code: 'unbuilt' for code in dead}
    dst = os.path.join(_HERE, 'wc3_misc.json')
    with open(dst, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, separators=(',', ':'), sort_keys=True)
        fh.write('\n')
    print('wrote %s: %d unbuilt unit codes (of %d units; %d producible; %d of the dead are ability-summoned)'
          % (dst, len(dead), len(units), len(producible), summoned))


if __name__ == '__main__':
    main()
