#!/usr/bin/python
"""AoE2:DE game module generator -- data + static-site build for the hotkey editor.

The hotkey editor is a single self-contained web page that does all .hkp parsing/
writing in the browser -- there is no server.  This is the AoE2 game's own toolchain
(other games get their own generator under games/<game>/):

    python3 games/aoe2/game_module_generator.py --regen   # rebuild the 3 json data files from a game install
    python3 games/aoe2/game_module_generator.py --build   # inline page.html + the json -> site/aoe2/index.html (default)

The UI shell is the repo-root page.html; --build inlines this game's json data into it
(via the shared page_assembler) to produce the deployable site/aoe2/index.html, and
refreshes the site/index.html launcher.  Binary .hkp logic lives in this folder's
hkp_parser.py (the CLI / round-trip oracle); the browser uses an equivalent JS port
embedded in page.html.

Stdlib only (works on Python 3.7).
"""
import glob
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))            # games/aoe2/
_ROOT = os.path.dirname(os.path.dirname(_HERE))               # repo root
_DATA_DIR = os.path.join(_HERE, 'data')                       # this game's vendored json
_GAME_SLUG = 'aoe2'
_GAME_NAME = 'AoE2:DE'

sys.path.insert(0, _ROOT)                                     # for the shared page_assembler
import page_assembler                                         # noqa: E402


# --- vendored static data, all generated from a game install by `--regen` ------
# These three files make the site fully self-contained: nothing is read from the
# game install at runtime, and `--build` inlines them into site/index.html.  Rebuild
# them after a game patch with `python3 hotkey_editor.py --regen`.
#   strings.json  : {hotkey string id -> display name}  (trimmed from the game tables)
#   card_data.json: {byId:{id:[group,ctx]}, chronicles, hidden}  (curation over hotkeys.json)
#   civ_data.json : {civCount, idToCivs:{id:[civs]}, units:[ids]}  (per-civ availability)

# Full game string table {id: name}; populated only during --regen, unused at runtime.
STRINGS = {}

# --- install paths used ONLY by --regen (never at runtime) --------------------
# command-id -> building/command-card name comes from the game's own hotkeys.json
# (authoritative; the group->name link the .hkp lacks); per-civ availability comes
# from the CivTechTrees/ + civilizations.json data; both live under .../_common/dat.
_DAT_REL = os.path.join('resources', '_common', 'dat')
_HOTKEYS_REL = os.path.join(_DAT_REL, 'hotkeys.json')


# --- game string table (hotkey id -> human readable name) --------------

# The .hkp only stores numeric string ids; the English names live in the game's
# key-value string table.  Auto-detect it across common install locations.
_STRING_REL = os.path.join('resources', 'en', 'strings', 'key-value',
                           'key-value-strings-utf8.txt')
_INSTALL_CANDIDATES = [
    r'D:\SteamLibrary\steamapps\common\AoE2DE',
    r'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE',
    r'C:\Program Files\Steam\steamapps\common\AoE2DE',
    r'C:\SteamLibrary\steamapps\common\AoE2DE',
    r'E:\SteamLibrary\steamapps\common\AoE2DE',
]
_STR_LINE = re.compile(r'\s*(\d+)\s+"(.*)"')


def _read_strings_file(path, names, override):
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = _STR_LINE.match(line)
            if m:
                sid = int(m.group(1))
                if override or sid not in names:
                    names[sid] = m.group(2)


def load_strings():
    """Return {id: name} from the game's English string tables.

    Loads the main key-value table first, then merges sibling key-value tables
    (e.g. the 'paphos'/Chronicles DLC) so newer hotkeys get real names instead
    of a raw id.  The main table wins on conflicts.  Campaign string files are
    excluded on purpose -- they hold scenario dialogue that could mis-name a
    hotkey id.
    """
    main = os.environ.get('AOE2_STRINGS')
    if not main:
        for root in _INSTALL_CANDIDATES:
            cand = os.path.join(root, _STRING_REL)
            if os.path.isfile(cand):
                main = cand
                break
    names = {}
    if main and os.path.isfile(main):
        _read_strings_file(main, names, override=True)
        folder = os.path.dirname(main)
        sibs = sorted(glob.glob(os.path.join(folder, 'key-value*strings-utf8.txt')))
        extra = 0
        for sib in sibs:
            if os.path.abspath(sib) != os.path.abspath(main):
                before = len(names)
                _read_strings_file(sib, names, override=False)
                extra += len(names) - before
        print('loaded %d hotkey names from %s (+%d from DLC tables)'
              % (len(names), os.path.basename(main), extra))
    else:
        print('WARNING: game string table not found; hotkeys will show numeric '
              'ids only.  Set AOE2_STRINGS=<path to key-value-strings-utf8.txt> '
              'to fix.')
    return names


# --- our own curation layered on the authoritative hotkeys.json ---------
# Each command gets [display group, conflict context].  Context codes:
#   G = always-active global ; R = replay ; CAMP = campaign (hidden)
#   U:<type> = unit selected (any/villager/military/siege/monk/trade) — different
#              unit types are mutually exclusive; 'any' overlaps all types
#   B:<tab>  = villager build menu tab (eco/mil) — tabs are mutually exclusive
#   D:<card> = building selected (a specific card, or 'any' for all buildings)
# The big base UNIT_COMMAND_HOTKEYS group is split by data_name:
_ABILITY = {
    'BUILD_ECONOMIC': ('Villager Commands', 'U:villager'),
    'BUILD_MILITARY': ('Villager Commands', 'U:villager'),
    'BUILD_MENU': ('Villager Commands', 'U:villager'),
    'REPAIR': ('Villager Commands', 'U:villager'),
    'DROPOFF_RESOURCES': ('Villager Commands', 'U:villager'),
    'SEEK_SHELTER': ('Villager Commands', 'U:villager'),
    'STOP': ('Unit Commands', 'U:any'),
    'GARRISON': ('Unit Commands', 'U:nonsiege'),     # siege units can't garrison

    'UNGARRISON': ('Garrisons/Transports', 'T:gt'),      # garrison-holders + transports only
    'UNLOAD': ('Garrisons/Transports', 'T:gt'),          # transports + siege towers + garrison buildings
    'NEXT_PAGE': ('Dock', 'D:Dock'),                 # "More Items" — the Dock's second command page
    'DELETE_UNIT': ('Unit Commands', 'U:any'),
    'DELETE_UNITS': ('Unit Commands', 'U:any'),
    'UNLOAD_RAM': ('Siege Commands', 'U:siege'),
    'PACK': ('Siege Commands', 'U:siege'),
    'UNPACK': ('Siege Commands', 'U:siege'),
    'ATTACK_GROUND': ('Siege Commands', 'U:siege'),
    'TRANSFORM': ('Hybrid Units', 'U:hybrid'),       # Change Mode — a few transform units
    'TRANSFORM_INTO': ('Hybrid Units', 'U:hybrid'),  # Change Mode (2)
    'HEAL': ('Monk Commands', 'U:monk'),
    'CONVERT': ('Monk Commands', 'U:monk'),
    'DROP_RELIC': ('Monk Commands', 'U:monk'),
    'BUILDING_SET_GATHER_POINT': ('Production Buildings', 'D:any'),
    'REMOVE_GATHER_POINT': ('Production Buildings', 'D:any'),
    'SET_GATHER_POINT_ON_SELF': ('Production Buildings', 'D:any'),
    'FORTIFIED_CHURCH_GO_BACK_TO_WORK': ('Dock', 'D:Dock'),   # go back to work (church/dock)
    'SHIP_TRADE_WOOD_1': ('Trade Commands', 'U:trade'),
    'SHIP_TRADE_WOOD_2': ('Trade Commands', 'U:trade'),
    'SHIP_TRADE_WOOD_3': ('Trade Commands', 'U:trade'),
}
# always-active shared groups (profile menus) -> (group, ctx); CYCLE merges into Go-To
_SHARED = {
    'UNIT_COMMAND_HOTKEYS': ('Unit Commands', 'U:any'),
    'GAME_COMMAND_HOTKEYS': ('Game Commands', 'G'),
    'CYCLE_COMMAND_HOTKEYS': ('Go-To Commands', 'G'),
    'SCROLL_HOTKEYS': ('Scroll Commands', 'G'),
    'ZOOM_HOTKEYS': ('Zoom Commands', 'G'),
    'SPECTATOR_HOTKEYS': ('Spectator/Replay Commands', 'R'),
    'GATE_HOTKEYS': ('Gate Commands', 'D:gate'),
}

# Battle for Greece (Chronicles) content. Its remappable hotkeys occupy the 419000+
# string-id block (War Chariot, Hoplite, Phalangite, Polemarch, the ships, the hero
# select/go-to commands, the Recruitment-Doctrine/Satrapy/Policy techs, …), and four
# command cards exist only in that mode: Fort/Port/Shipyard/Outpost — the Greek/Persian
# Castle/Dock equivalents, whose slots reuse a few base-id names (Conscription, fish
# traps). We hide all of it by default like the campaign menus, but keep each command's
# real group/context so conflict checks still work if the user toggles Chronicles on.
# NB: the handful of general commands down at 400000-400021 (Seek Shelter / Drop Off
# Resources / All Back to Work) are NOT Battle-for-Greece — they sit below this block
# and are already curated as Villager/Town Center commands, so they stay visible.
_BFG_ID_MIN = 419000
_BFG_CARDS = ('FORT_HOTKEYS', 'PORT_HOTKEYS', 'SHIPYARD_HOTKEYS', 'OUTPOST_HOTKEYS')


def _is_bfg(cid, dn):
    return dn in _BFG_CARDS or (cid is not None and cid >= _BFG_ID_MIN)


def _ctrl_split(name):
    m = re.search(r'#(\d+)', name or '')
    return 'Control Groups 11-20' if (m and int(m.group(1)) >= 11) else 'Control Groups 1-10'


def build_card_data():
    """Read hotkeys.json (authoritative) and emit {byId:{id:[group,ctx]}, chronicles,
    hidden} with our curation layered on top.  Regen only -- raises if no install."""
    path = os.environ.get('AOE2_HOTKEYS')
    if not path:
        for root in _INSTALL_CANDIDATES:
            cand = os.path.join(root, _HOTKEYS_REL)
            if os.path.isfile(cand):
                path = cand
                break
    if path and os.path.isfile(path):
        try:
            d = json.load(open(path, encoding='utf-8'))
            by_id = {}
            chron = set()
            hidden = set()   # always-hidden, regardless of the Chronicles toggle

            def put(cid, group, ctx):
                if cid is not None:
                    by_id[str(cid)] = [group, ctx]

            for g in d.get('shared_hotkey_group_list', []):
                dn = g.get('data_name')
                for c in g.get('hotkey_list', []):
                    cid = c.get('name_string_id')
                    nm = STRINGS.get(cid, '')
                    if _is_bfg(cid, dn):
                        chron.add(cid)   # e.g. the Battle for Greece hero select/go-to commands
                    if dn == 'GROUP_COMMAND_HOTKEYS':
                        put(cid, _ctrl_split(nm), 'G')
                    elif dn == 'MILITARY_UNITS_HOTKEYS':
                        cdn = c.get('data_name')
                        if cdn == 'BUILD_MENU':
                            put(cid, 'Villager Commands', 'U:villager')
                            hidden.add(cid)   # redundant generic "Build" — eco/mil build menus cover it
                        elif cdn == 'AUTO_SCOUT':
                            put(cid, 'Military Unit Commands', 'X:autoscout')  # scout toggle; coexists with Stop
                        else:
                            put(cid, 'Military Unit Commands', 'U:military')
                    elif dn in _SHARED:
                        put(cid, *_SHARED[dn])
                    else:
                        put(cid, STRINGS.get(g.get('name_string_id')) or 'Other', 'G')

            for g in d.get('hotkey_group_list', []):
                dn = g.get('data_name')
                gname = STRINGS.get(g.get('name_string_id'))
                camp = str(dn).startswith('CAMPAIGN')
                for c in g.get('hotkey_list', []):
                    cid = c.get('name_string_id')
                    if cid is None:
                        continue
                    if camp:
                        chron.add(cid)
                        put(cid, gname or 'Campaign', 'CAMP')
                        continue
                    if _is_bfg(cid, dn):
                        chron.add(cid)   # Battle for Greece: hidden by default, real group kept below
                    if dn == 'UNIT_COMMAND_HOTKEYS':
                        put(cid, *_ABILITY.get(c.get('data_name'), ('Unit Commands', 'U:any')))
                    elif dn == 'GAME_COMMAND_HOTKEYS':
                        put(cid, 'Select Commands', 'G')
                    elif dn == 'CYCLE_COMMAND_HOTKEYS':
                        put(cid, 'Go-To Commands', 'G')
                    elif dn == 'VILLAGER_HOTKEYS':
                        if c.get('data_name') == 'VILLAGER_BUILD_FISH_TRAP':
                            put(cid, 'Fishing Ship Build', 'U:fishing')   # built by fishing ships, not villagers
                        elif c.get('context') == 'military':
                            put(cid, 'Build Military Buildings', 'B:mil')
                        else:
                            put(cid, 'Build Economic Buildings', 'B:eco')
                    elif gname:
                        put(cid, gname, 'D:' + gname)
            print('card data: %d command ids grouped from hotkeys.json' % len(by_id))
            return json.dumps({'byId': by_id, 'chronicles': sorted(chron),
                               'hidden': sorted(hidden)})
        except Exception as e:
            raise RuntimeError('failed to build card data from hotkeys.json: %s' % e)
    raise RuntimeError('hotkeys.json not found; set AOE2_HOTKEYS or install the game')


# --- per-civ availability (regen only) ----------------------------------------
def _norm_name(s):
    """Normalise a unit/building/tech name for matching (mirrors the old frontend
    normName): drop a trailing ', X' alias, a leading 'Tech:' and a trailing
    '-line', then lowercase."""
    n = s.split(',')[0].strip()
    n = re.sub(r'^Tech:\s*', '', n, flags=re.I).strip()
    n = re.sub(r'-line$', '', n, flags=re.I).strip()
    return n.lower()


def _hotkey_string_ids(hk):
    """All name_string_ids referenced by hotkeys.json (groups + commands)."""
    ids = set()
    for lst in ('shared_hotkey_group_list', 'hotkey_group_list'):
        for g in hk.get(lst, []):
            if g.get('name_string_id') is not None:
                ids.add(g['name_string_id'])
            for c in g.get('hotkey_list', []):
                if c.get('name_string_id') is not None:
                    ids.add(c['name_string_id'])
    return ids


def build_civ_data(dat_dir, hotkey_ids):
    """Build {civCount, idToCivs, units} from the install's per-civ tech trees.

    A civ has a unit/building/tech iff its CivTechTrees/<CIV>.json lists that node
    with Node Status != 'NotAvailable'.  We map each node to the hotkey command ids
    by normalised name (the tech-tree node's own string id differs from the hotkey
    id), so the runtime can look up availability by id alone -- no name matching.
    """
    civmeta = json.load(open(os.path.join(dat_dir, 'civilizations.json'),
                             encoding='utf-8'))['civilization_list']
    civs = []   # (display name, tech-tree filename) for the standard ranked civs
    for c in civmeta:
        if c.get('era') != 'base' or c.get('tech_tree_name') == 'GAIA':
            continue                       # skip Gaia and the 'antiquity' Chronicles civs
        disp = STRINGS.get(c.get('name_string_id')) or c.get('internal_name')
        civs.append((disp, c.get('tech_tree_name')))
    name2civs = {}
    unit_names = set()
    for disp, tt in civs:
        tree = json.load(open(os.path.join(dat_dir, 'CivTechTrees', tt + '.json'),
                              encoding='utf-8'))
        for node in tree.get('civ_techs_buildings', []) + tree.get('civ_techs_units', []):
            if node.get('Node Status') == 'NotAvailable':
                continue
            nm = _norm_name(node.get('Name') or '')
            if not nm:
                continue
            name2civs.setdefault(nm, set()).add(disp)
            if node.get('Use Type') == 'Unit':
                unit_names.add(nm)
    id_to_civs = {}
    unit_ids = []
    for cid in sorted(hotkey_ids):
        nm = _norm_name(STRINGS.get(cid, ''))
        if nm in name2civs:
            id_to_civs[str(cid)] = sorted(name2civs[nm])
            if nm in unit_names:
                unit_ids.append(cid)
    print('civ data: %d civs, %d ids mapped (%d units)'
          % (len(civs), len(id_to_civs), len(unit_ids)))
    return json.dumps({'civCount': len(civs), 'idToCivs': id_to_civs,
                       'units': sorted(unit_ids)}, ensure_ascii=False)


def _find_dat_dir():
    """Locate the install's resources/_common/dat directory (regen only)."""
    env = os.environ.get('AOE2_HOTKEYS')
    if env and os.path.isfile(env):
        return os.path.dirname(env)
    for root in _INSTALL_CANDIDATES:
        cand = os.path.join(root, _DAT_REL)
        if os.path.isdir(cand):
            return cand
    return None


def regen():
    """Rebuild the three vendored data files from a game install."""
    global STRINGS
    STRINGS = load_strings()
    if not STRINGS:
        print('ERROR: game string table not found; set AOE2_STRINGS.')
        return 1
    dat = _find_dat_dir()
    if not dat:
        print('ERROR: game data dir not found; set AOE2_HOTKEYS to .../dat/hotkeys.json')
        return 1
    card = build_card_data()
    hk = json.load(open(os.path.join(dat, 'hotkeys.json'), encoding='utf-8'))
    ids = _hotkey_string_ids(hk)
    strings_out = json.dumps({str(i): STRINGS[i] for i in sorted(ids) if i in STRINGS},
                             ensure_ascii=False)
    civ = build_civ_data(dat, ids)
    for fname, data in (('strings.json', strings_out), ('card_data.json', card),
                        ('civ_data.json', civ)):
        with open(os.path.join(_DATA_DIR, fname), 'w', encoding='utf-8') as f:
            f.write(data)
        print('wrote %s (%d KB)' % (fname, len(data.encode('utf-8')) // 1024))
    return 0


# --- build the single-file site ----------------------------------------

def build():
    """Assemble the self-contained site/aoe2/index.html from page.html + module.js + json.

    The launcher is the orchestrator's job (build.py / page_assembler.build_all), so
    this only writes this game's page.  Returns (slug, name) on success, or None on
    failure -- the contract page_assembler.discover_games()/build_all() rely on.
    """
    page_path = os.path.join(_ROOT, 'page.html')
    module_path = os.path.join(_HERE, 'module.js')   # this game's engine-injected code
    try:
        data = {
            'strings': json.load(open(os.path.join(_DATA_DIR, 'strings.json'), encoding='utf-8')),
            'civ': json.load(open(os.path.join(_DATA_DIR, 'civ_data.json'), encoding='utf-8')),
            'card': json.load(open(os.path.join(_DATA_DIR, 'card_data.json'), encoding='utf-8')),
        }
        module_js = open(module_path, encoding='utf-8').read()
    except FileNotFoundError as e:
        print('ERROR: missing data file (%s); run --regen first.' % e.filename)
        return None
    site_dir = os.path.join(_ROOT, 'site')     # deployable (e.g. Cloudflare Pages output dir)
    out_path = os.path.join(site_dir, _GAME_SLUG, 'index.html')
    try:
        nbytes = page_assembler.assemble(page_path, data, out_path, module_js, _GAME_SLUG)
    except RuntimeError as e:
        print('ERROR: %s' % e)
        return None
    print('wrote site/%s/index.html (%d KB)' % (_GAME_SLUG, nbytes // 1024))
    return (_GAME_SLUG, _GAME_NAME)


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--regen' in args:
        sys.exit(regen())
    if '--build' in args or not args:
        # Build just this game, then refresh the launcher across every built game so it
        # stays complete (use build.py to (re)build all games at once).
        if build() is None:
            sys.exit(1)
        page_assembler.write_launcher_for_built(_ROOT)
        print('wrote site/index.html (launcher)')
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
