#!/usr/bin/env python3
"""Generate data/wc3_cards.json: each unit's command card, compiled from Blizzard's own game data.

The editor groups hotkeys by the in-game command card a command sits on.  Those cards used to come
from jcfieldsdev's hand-curated `wc3.json` `commands`, which has errors (it labels the Obsidian
Statue's morph under the Destroyer *unit* code `ubsp`, which has no command button, instead of the
real ability `aave`) and gaps (it misses the Barracks' `rhsb`).  This generator instead reconstructs
each card straight from the source SLK/func tables -- the same data the game builds the card from --
and keeps jcfields only as a cross-check (printed as a diff at the end).

A unit U's card =
  - its produced things: `Trains` / `Researches` / `Upgrade` / `Revive` from the `*unitfunc.txt`
    profiles (NOT `Builds` -- those live on the worker's separate Build sub-menu, see below);
  - its abilities: `abilList` + `heroAbilList` from `unitabilities.slk`, filtered to ones that have a
    real command-card button (a Buttonpos / Researchbuttonpos, via positions.json);
  - its ALTERNATE-FORM abilities: when U has a *morph* ability (it transforms into another unit -- Bear
    Form, Destroyer Form, Robo-Goblin, Stone Form, Metamorphosis, …), that form's button-abilities are
    unioned in, so both forms' hotkeys show on the one card.  A morph is told apart from a *summon*
    (Summon Water Elemental, Raise Dead, …) structurally: a morph ability references the caster itself
    in its `DataA*`/`UnitID*` fields (a self / two-way transform), a summon only references the spawned
    unit.  This is why the Tinker regains `ande` Demolish while the Archmage does NOT gain the Water
    Elemental's abilities.
  - the engine command scaffolding jcfields put on the card (`cmdbuild*` Build button, `cmdcancel*`
    Cancel, `cmdattackground`) -- these are engine commands with no unit/ability data of their own, so
    they're carried over verbatim.  (`cmdrally` is intentionally dropped: it's promoted to the shared
    "Common — Building Commands" card in module.js.)

The Build sub-menu units (`cmdbuild*`, jcfields type `other`) get their card = the union of the
`Builds=` lists of the workers that open them, ordered by slot, + `cmdcancel`.

Card entries are ordered by their command-card slot (Buttonpos), matching the in-game layout.  Names
come from the game strings (wc3_names.json) with the jcfields label as a fallback; module.js re-resolves
the name through the same strings at render time, so the stored name is only a safety net.

Run from anywhere:  python3 games/Warcraft3/data/gen_wc3_cards.py
Reads:  data/slk data/unitabilities.slk + unitskin.txt + abilitydata.slk + *unitfunc.txt,  data/positions.json,
        data/wc3_names.json,  data/wc3.json (jcfields: unit list / types / build links / cross-check)
Writes: data/wc3_cards.json     (+ prints a jcfields cross-check diff)
"""
import glob
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, 'slk data')
_CMD_RE = re.compile(r'^cmd', re.I)
# engine-command scaffolding lifted into the shared "Common — Building Commands" card in module.js,
# so we don't carry it onto individual cards
_PROMOTED = frozenset(('cmdrally', 'cmdcancelbuild'))


def parse_slk(path):
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


def slk_cols(rows):
    return {name: x for x, name in rows.get(1, {}).items()}


def load_unit_abilities():
    """unit -> ability codes, merging unitabilities.slk (`abilList`+`heroAbilList`) with the Reforged
    skin lists in unitskin.txt (`abilSkinList`).  The skin lists are more current/complete -- e.g. they
    carry Call to Arms (`amic`) on the base Town Hall, Purge on the Shaman, Possession on the Banshee,
    which the older `abilList` is missing -- so we union skin-only abilities in (nothing is dropped)."""
    rows = parse_slk(os.path.join(_SRC, 'unitabilities.slk'))
    col = slk_cols(rows)
    idc, ab, hb = col['unitAbilID'], col.get('abilList'), col.get('heroAbilList')
    out = {}
    for y, row in rows.items():
        if y == 1:
            continue
        uid = str(row.get(idc, '')).lower()
        if not uid:
            continue
        codes = []
        for c in (ab, hb):
            if c and row.get(c):
                codes += [x.strip().lower() for x in str(row[c]).split(',') if x.strip()]
        out[uid] = codes
    # merge the skin ability lists (abilSkinList, preferring the melee variant)
    cur = None
    with open(os.path.join(_SRC, 'unitskin.txt'), encoding='latin-1') as fh:
        skin = {}
        for line in fh:
            line = line.rstrip('\r\n')
            m = re.match(r'^\[(.*?)\]', line)
            if m:
                cur = m.group(1).lower()
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            if cur and key in ('abilSkinList', 'abilSkinList:melee,V0'):
                codes = [c.strip().lower() for c in val.split(',') if c.strip()]
                if key == 'abilSkinList:melee,V0' or cur not in skin:   # melee variant wins
                    skin[cur] = codes
    for uid, codes in skin.items():
        base = out.setdefault(uid, [])
        for c in codes:
            if c not in base:
                base.append(c)
    return out


def load_ability_unit_refs(unit_codes):
    """ability -> set of unit codes it references in DataA*/DataB*/DataC*/UnitID* (morph/summon targets)."""
    rows = parse_slk(os.path.join(_SRC, 'abilitydata.slk'))
    col = slk_cols(rows)
    idc = col['alias']
    refcols = [x for name, x in col.items()
               if name and (name.startswith('UnitID') or name.startswith('DataA')
                            or name.startswith('DataB') or name.startswith('DataC'))]
    out = {}
    for y, row in rows.items():
        if y == 1:
            continue
        a = str(row.get(idc, '')).lower()
        refs = set()
        for x in refcols:
            v = str(row.get(x, '')).lower()
            if len(v) == 4 and v in unit_codes:
                refs.add(v)
        if a:
            out[a] = refs
    return out


def load_production():
    """unit -> {key: [codes]} for the card-producing lists in the *unitfunc.txt profiles.  Builds is
    the worker's separate build sub-menu; the rest sit directly on the unit's card (Sellunits/Sellitems
    are a shop's / shipyard's / tavern's hire+purchase stock)."""
    keys = ('Builds', 'Trains', 'Upgrade', 'Researches', 'Revive', 'Sellunits', 'Sellitems')
    out = {}
    for name in sorted(os.listdir(_SRC)):
        if not name.lower().endswith('unitfunc.txt'):
            continue
        cur = None
        with open(os.path.join(_SRC, name), encoding='latin-1') as fh:
            for line in fh:
                line = line.rstrip('\r\n')
                m = re.match(r'^\[(.*?)\]', line)
                if m:
                    cur = m.group(1).lower()
                    continue
                if not cur:
                    continue
                for key in keys:
                    if line.startswith(key + '='):
                        for c in line[len(key) + 1:].split(','):
                            c = c.strip().lower()
                            if len(c) == 4:                      # skip blanks / '_' / bare numbers
                                out.setdefault(cur, {}).setdefault(key, []).append(c)
    return out


def main():
    data = json.load(open(os.path.join(_HERE, 'wc3.json'), encoding='utf-8'))
    units = data['units']
    names = json.load(open(os.path.join(_HERE, 'wc3_names.json'), encoding='utf-8'))
    pos = json.load(open(os.path.join(_HERE, 'positions.json'), encoding='utf-8'))
    uab = load_unit_abilities()
    # the unit-code universe for morph/summon ref detection must include source-only alternate-form
    # units (e.g. the Robo-Goblin form `nrob`, which carries Demolish but isn't a jcfields unit),
    # so union unitabilities' keys with the jcfields unit list.
    unit_codes = set(units.keys()) | set(uab.keys())
    arefs = load_ability_unit_refs(unit_codes)
    prod = load_production()

    def has_button(code):
        return code in pos['b'] or code in pos['r']

    def slot(code):
        s = pos['b'].get(code)
        if s is None:
            s = pos['r'].get(code)
        return s if s is not None else 99

    # jcfields label fallback: code -> a name jcfields used anywhere (for the ~few codes the game
    # strings don't cover, e.g. custom a000/aell abilities)
    jc_name = {}
    for u in units.values():
        for c in u.get('commands', []):
            jc_name.setdefault(c[0].lower(), c[1])

    def label(code):
        return names.get(code) or jc_name.get(code) or code

    def abilities_of(u):
        """(code, form) pairs: u's own button-abilities (form='') + its morph alternate-form
        button-abilities tagged with the alt unit's code (summons excluded).  The form tag lets the
        editor scope conflicts per form -- a base-form ability never clashes with an alt-form one,
        since the unit is only ever in one form at a time."""
        own = uab.get(u, [])
        tagged = [(c, '') for c in own]
        for a in own:
            if u in arefs.get(a, ()):                            # self/two-way transform => morph
                for alt in sorted(arefs[a] - {u}):
                    tagged += [(c, alt) for c in uab.get(alt, [])]
        seen, out = set(), []
        for c, form in tagged:
            if c not in seen and has_button(c):
                seen.add(c)
                out.append((c, form))
        return out

    # workers -> their Build sub-menu unit (jcfields `build` link); reverse it so each sub-menu unit
    # collects the Builds= of every worker that opens it.
    builders = {u: units[u]['build'] for u in units if units[u].get('build')}
    submenu_builds = {}
    for worker, menu in builders.items():
        for b in prod.get(worker, {}).get('Builds', []):
            submenu_builds.setdefault(menu, [])
            if b not in submenu_builds[menu]:
                submenu_builds[menu].append(b)

    cards = {}
    diffs = []
    for u in units:
        if u in submenu_builds:                                  # a Build sub-menu unit (cmdbuild*)
            tagged = [(c, '') for c in sorted(submenu_builds[u], key=slot)]
            tagged += [(c[0].lower(), '') for c in units[u].get('commands', []) if c[0].lower().startswith('cmdcancel')]
        else:
            p = prod.get(u, {})
            real = []                                            # (code, form) pairs
            for k in ('Trains', 'Researches', 'Upgrade', 'Revive', 'Sellunits', 'Sellitems'):
                real += [(c, '') for c in p.get(k, [])]
            real += abilities_of(u)
            # dedup by code AND by display name: WC3 has several rawcodes for one ability (Abolish
            # Magic acdm/acd2, Bash anbh/acbh, …) and a unit's merged abilList+abilSkinList can carry
            # two of them -- keep the first (abilList/base-form order) so the ability shows once.
            seen, seen_names, ordered = set(), set(), []
            for c, form in real:
                nm = label(c)
                if c in seen or nm in seen_names:
                    continue
                seen.add(c)
                seen_names.add(nm)
                ordered.append((c, form))
            ordered.sort(key=lambda cf: slot(cf[0]))
            # carry over jcfields engine-command scaffolding (Build button, Cancel, Attack Ground);
            # drop cmdrally (promoted to the shared building-commons card in module.js)
            scaffold = [(c[0].lower(), '') for c in units[u].get('commands', [])
                        if _CMD_RE.match(c[0]) and c[0].lower() not in _PROMOTED and c[0].lower() not in seen]
            tagged = ordered + scaffold
            # cross-check vs jcfields (real commands only, i.e. excluding cmd* scaffolding)
            jc_real = [c[0].lower() for c in units[u].get('commands', []) if not _CMD_RE.match(c[0])]
            added = [c for c, _ in ordered if c not in jc_real]
            removed = [c for c in jc_real if c not in {c for c, _ in ordered}]
            if added or removed:
                diffs.append((u, units[u]['name'], added, removed))
            # fall back to jcfields if source produced nothing (custom/campaign units source misses)
            if not ordered and jc_real:
                tagged = [(c[0].lower(), '') for c in units[u].get('commands', [])]
        if tagged:
            # entry = [code, name] (base) or [code, name, form] (alt-form ability)
            cards[u] = [[c, label(c)] + ([form] if form else []) for c, form in tagged]

    dst = os.path.join(_HERE, 'wc3_cards.json')
    with open(dst, 'w', encoding='utf-8') as fh:
        json.dump(cards, fh, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        fh.write('\n')
    print('wrote %s: %d unit cards' % (dst, len(cards)))

    # cross-check report
    print('\n=== jcfields cross-check: %d units where source differs (real commands only) ===' % len(diffs))
    for u, nm, added, removed in sorted(diffs):
        a = ' +[' + ','.join('%s(%s)' % (c, label(c)) for c in added) + ']' if added else ''
        r = ' -[' + ','.join('%s(%s)' % (c, label(c)) for c in removed) + ']' if removed else ''
        print('  %-5s %-28s%s%s' % (u, nm[:28], a, r))


if __name__ == '__main__':
    main()
