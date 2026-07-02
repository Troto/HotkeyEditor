#!/usr/bin/python
"""Match bundled AoE2 command icons to command ids -> data/aoe2_icons.json.

The `icons/` folder holds wiki-style AoE2 UI icons named by unit / building / tech / hero (e.g.
`Barracks_aoe2DE.png`, `Camelrider_aoe2DE.png`, `BallisticsDE.png`).  A command's display name
(`strings.json`) usually contains that noun, so we match by NORMALISED NAME: strip the icon
filename's decoration (`_aoe2DE`, `Icon`, `-DE`, trailing `de`, ...) to a bare key, then try a few
normalised candidates off each carded command's name (the whole thing, minus a leading verb like
"Select all"/"Go to"/"Tech:", each comma/slash segment, `-line` stripped, first word) and take the
first that hits an icon.  Output is `{ "<command id>": "<icon basename>" }` for the module's
`iconOf` (the keyboard ability-card icon overlay -- see module.js / games/Warcraft3 for the model).

Only base-game units/techs/buildings tend to match; utility commands (scroll/zoom/control groups)
and campaign/scenario units the icon set doesn't cover simply get no icon (that's fine -- the
overlay just skips them).  Matching is name-based and best-effort; the OVERRIDES map below pins or
corrects individual ids.  Stdlib only (Python 3.7); no game install needed.

Usage: python3 gen_aoe2_icons.py   (writes data/aoe2_icons.json next to this script)
"""
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))

# id -> icon basename (no extension) to force/repair a specific match; '' means "no icon".
OVERRIDES = {}

# command display-name -> icon basename, applied to EVERY id with that exact name (a command
# repeats across cards, so this is keyed by name, not id).  These are matches the name heuristic
# misses: genuine misses (Villager, the base Tower/Demolition Ship, Sappers, the unique-tech
# slots) plus one representative icon per Blacksmith/eco UPGRADE LINE (the commands name the whole
# line -- "Tech: Melee Attack Upgrades" -- so we show the line's first tier; the other tiers'
# icons are redundant and were removed).  Age Up uses one of the four age icons.
NAME_OVERRIDES = {
    'Villager': 'MaleVillDE',
    'Tower': 'Watch_Tower_icon_AoE2DE',            # base tower (Guard Tower / Keep are upgrades)
    'Tech: Age Up': 'FeudalAgeIconDE',
    'Demolition Ship': 'Demoship_aoe2DE',          # base of the demo-ship line
    'Tech: Sappers': 'SapperDE',
    'Tech: Unique Castle Technology': 'UniqueTechCastle-DE',
    'Tech: Unique Imperial Technology': 'UniqueTechImperialDE',
    'Tech: Melee Attack Upgrades': 'Forging_aoe2de',
    'Tech: Arrow Attack Upgrades': 'FletchingDE',
    'Tech: Infantry Armor Upgrades': 'ScaleMailArmorDE',
    'Tech: Cavalry Armor Upgrades': 'ScaleBardingArmorDE',
    'Tech: Archer Armor Upgrades': 'PaddedArcherArmorDE',
    'Tech: Gold Upgrades': 'GoldMiningDE',
    'Tech: Stone Upgrades': 'StoneMiningDE',
    'Tech: Wood Upgrades': 'DoubleBitAxe_aoe2DE',
}

_MARKERS = ['aoe2de', 'aoe2', 'icon', 'updated', '_new', 'llama']


def icon_key(basename):
    """Normalise an icon filename to a bare comparison key (drop decoration + trailing 'de')."""
    x = basename.lower()
    for m in _MARKERS:
        x = x.replace(m, '')
    x = re.sub(r'[^a-z0-9]+', '', x)
    x = re.sub(r'(?:de)+$', '', x)
    return x


def cmd_key(text):
    return re.sub(r'[^a-z0-9]+', '', re.sub(r'-line', '', text, flags=re.I).lower())


def candidates(name):
    """Ordered, de-duped normalised keys to try for a command name (most specific first)."""
    n = re.sub(r'\(.*?\)', '', name)                       # drop "(Campaign Only)" etc.
    n = re.sub(r'^\s*Tech:\s*', '', n, flags=re.I).strip()
    out = []

    def add(x):
        k = cmd_key(x)
        if k and k not in out:
            out.append(k)

    add(n)
    base = re.sub(r'^(Select all|Go to|Build|Train|Rebuild|Reseed|Sell \d+|Buy \d+)\s+', '',
                  n, flags=re.I)
    if base != n:
        add(base)
    for seg in re.split(r'[,/]', base):                    # "Knight-line, Hei Guang Cavalry" -> Knight
        add(seg.strip())
    add(base.strip().split(' ')[0] if base.strip() else '')  # first-word fallback
    return out


def build():
    strings = json.load(open(os.path.join(_HERE, 'strings.json'), encoding='utf-8'))
    card = json.load(open(os.path.join(_HERE, 'card_data.json'), encoding='utf-8'))
    by_id = card['byId']
    icon_dir = os.path.join(_HERE, 'icons')
    icons = sorted(f[:-4] for f in os.listdir(icon_dir) if f.endswith('.png'))

    icon_map = {}                                          # normalised key -> basename (first wins, stable)
    for b in icons:
        k = icon_key(b)
        if k and k not in icon_map:
            icon_map[k] = b

    out = {}
    for cid, name in strings.items():
        if cid not in by_id:                              # only carded commands get an icon slot
            continue
        if cid in OVERRIDES:
            if OVERRIDES[cid]:
                out[cid] = OVERRIDES[cid]
            continue
        if name in NAME_OVERRIDES:
            out[cid] = NAME_OVERRIDES[name]
            continue
        for k in candidates(name):
            if k in icon_map:
                out[cid] = icon_map[k]
                break

    ordered = {cid: out[cid] for cid in sorted(out, key=lambda x: int(x) if x.isdigit() else x)}
    path = os.path.join(_HERE, 'aoe2_icons.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(ordered, f, separators=(',', ':'), ensure_ascii=False)
        f.write('\n')
    carded = sum(1 for cid in strings if cid in by_id)
    print('wrote %s (%d/%d carded commands matched, %d unique icons)'
          % (os.path.relpath(path, _HERE), len(ordered), carded, len(set(ordered.values()))))


if __name__ == '__main__':
    build()
