#!/usr/bin/env python3
"""Generate StarCraft II multiplayer hotkey data from extracted game files.

Reads the dependency-merged catalog for the LotV multiplayer mod chain
(core -> liberty -> libertymulti -> swarm -> swarmmulti -> void -> voidmulti)
and produces:

  data/sc2.json         structured units -> command cards -> buttons
  data/sc2_defaults.ini flat  <command>[/<unit>]=<key>  list (for validation
                        against the reference Sc2HotkeyData project)

This is a clean re-implementation of the process used by
https://github.com/BeedeBdoo/Sc2HotkeyData (xml_tree_merger.py / xml_tree_reader.py),
scoped to multiplayer and emitting JSON for the browser module.

Python 3.7 stdlib only.
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from copy import deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(HERE, "SC2 data", "HotkeyData")
STRINGS_ROOT = os.path.join(HERE, "SC2 data", "GameStrings", "mods")

# Multiplayer dependency chain, oldest first. Later mods override earlier ones.
MP_CHAIN = ["core", "liberty", "libertymulti", "swarm", "swarmmulti", "void", "voidmulti"]

HOTKEY_SUFFIXES = ("_SC1", "_NRS", "_USD", "_USDL")

# Command card grid: 5 columns x 3 rows.
GRID_COLS = 5
GRID_ROWS = 3


# --------------------------------------------------------------------------- paths
def mod_file(mod, *parts):
    return os.path.join(DATA_ROOT, mod + ".sc2mod", *parts)


def unitdata_path(mod):
    return mod_file(mod, "base.sc2data", "gamedata", "unitdata.xml")


def buttondata_path(mod):
    return mod_file(mod, "base.sc2data", "gamedata", "buttondata.xml")


def gamehotkeys_path(mod):
    return mod_file(mod, "enus.sc2data", "localizeddata", "gamehotkeys.txt")


def gamestrings_path(mod):
    return os.path.join(STRINGS_ROOT, mod + ".sc2mod",
                        "enus.sc2data", "localizeddata", "gamestrings.txt")


# --------------------------------------------------------------------------- text files
def parse_keyvalue_file(path):
    """Return list of (key, value) from a `key=value` text file (order preserved)."""
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.rstrip("\n\r")
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            out.append((key.strip(), value))
    return out


def load_gamehotkeys():
    """command id -> default key, merged across the chain (later mods win).

    Only `Button/Hotkey/<id>` entries; profile variants (_SC1/_NRS/_USD/_USDL)
    are dropped so we keep the Standard profile's key.
    """
    hk = {}
    for mod in MP_CHAIN:
        for key, value in parse_keyvalue_file(gamehotkeys_path(mod)):
            if not key.startswith("Button/Hotkey/"):
                continue
            cmd = key[len("Button/Hotkey/"):]
            if cmd.endswith(HOTKEY_SUFFIXES):
                continue
            hk[cmd] = value
    return hk


def load_strings():
    """Merged GameStrings: full 'Category/Kind/Id' key -> text."""
    strings = {}
    for mod in MP_CHAIN:
        for key, value in parse_keyvalue_file(gamestrings_path(mod)):
            strings[key] = value
    return strings


# --------------------------------------------------------------------------- xml helpers
def child_attrs(elem):
    """Flatten an element's own attributes plus `<Tag value="..."/>` children.

    SC2 data expresses fields either as attributes on LayoutButtons or as child
    elements with a `value` attribute; normalise both to a flat dict.
    """
    attrs = dict(elem.attrib)
    for child in elem:
        if "value" in child.attrib:
            attrs.setdefault(child.tag, child.attrib["value"])
    return attrs


# --------------------------------------------------------------------------- button data
def load_buttondata():
    """button id -> {universal, alias, hotkeyset, icon, hotkey}, merged."""
    buttons = {}
    for mod in MP_CHAIN:
        path = buttondata_path(mod)
        if not os.path.isfile(path):
            continue
        root = ET.parse(path).getroot()
        for cb in root:
            if cb.tag != "CButton":
                continue
            bid = cb.get("id")
            if bid is None:
                continue
            rec = buttons.setdefault(bid, {})
            for child in cb:
                val = child.get("value")
                if child.tag == "Universal":
                    rec["universal"] = val not in (None, "0", "")
                elif child.tag == "HotkeyAlias":
                    rec["alias"] = val
                elif child.tag == "HotkeySet":
                    rec["hotkeyset"] = val
                elif child.tag == "Icon":
                    rec["icon"] = val
                elif child.tag == "Hotkey":
                    # e.g. "Button/Hotkey/Foo" -> command id "Foo"
                    rec["hotkey"] = val.split("/")[-1] if val else val
    return buttons


def resolve_command(face, buttons, _seen=None):
    """Follow the HotkeyAlias/Hotkey chain from a Face button id to its root
    hotkey command id. Falls back to the face id itself."""
    if _seen is None:
        _seen = set()
    if face in _seen:
        return face
    _seen.add(face)
    rec = buttons.get(face)
    if rec:
        nxt = rec.get("alias") or rec.get("hotkey")
        if nxt and nxt != face:
            return resolve_command(nxt, buttons, _seen)
    return face


# --------------------------------------------------------------------------- unit data / card merge
def merge_button_attrs(dst, src):
    dst = dict(dst)
    for k, v in src.items():
        if v not in (None, ""):        # a partial patch (e.g. a faceless slot tweak) keeps prior attrs
            dst[k] = v
    return dst


def dedup_faces(slots):
    """Collapse an index-merged card to one button per Face, in slot order.

    The raw data can list the same Face many times (BurrowDown x12 on Hydralisk); a unit never
    actually shows a command twice on one card, so we keep a single entry per Face, merging in any
    non-empty attributes (Row/Column, Type, ...) from its other occurrences.
    """
    by_face = {}
    order = []
    for idx in sorted(slots):
        attrs = slots[idx]
        face = attrs.get("Face")
        if not face:
            continue
        if face not in by_face:
            by_face[face] = dict(attrs)
            order.append(face)
        else:
            by_face[face] = merge_button_attrs(by_face[face], attrs)
    return [by_face[f] for f in order]


def card_position(card, pos_map):
    """Array position (int) of a <CardLayouts>, assigned like SC2's positional array.

    An explicit `index` names the slot. A bare card (no index, no CardId) is the unit's main card,
    slot 0 -- so a dependency mod re-stating it, or a unit with several bare cards, all fold onto
    one main card. A `CardId` sub-card reuses its slot if already seen, else appends past the max.
    Mirrors the LayoutButtons logic one level up, and lets a later `index=N` patch (which omits the
    CardId) resolve to the same sub-card that occupies slot N.
    """
    idx = card.get("index")
    if idx is not None:
        return int(idx)
    cid = card.get("CardId")
    if not cid:
        return 0
    for p, key in pos_map.items():
        if key == cid:
            return p
    return (max(pos_map) + 1) if pos_map else 0


def sort_card_keys(keys):
    """Main pages (@0, @1, ...) first in index order, then CardId sub-cards alphabetically."""
    def rank(c):
        if c.startswith("@"):
            try:
                return (0, int(c[1:]), "")
            except ValueError:
                return (0, 0, c)
        return (1, 0, c)
    return sorted(keys, key=rank)


class UnitCatalog:
    """Accumulates dependency-merged unit command cards across the mod chain.

    State per unit id:
        fields: dict of scalar fields (SubgroupAlias, Race, ...)
        cards:  { card_key(str): { button_index(int): attrs } }
    """

    def __init__(self):
        self.units = {}  # id -> {"fields": {}, "cards": {}, "parent": str|None}

    def _unit(self, uid):
        # card_pos: array position (int) -> canonical card key, bridging SC2's positional
        # CardLayouts index to the CardId a later index-only patch omits (see _card_key).
        return self.units.setdefault(
            uid, {"fields": {}, "cards": {}, "card_pos": {}, "parent": None})

    def apply_mod(self, path):
        if not os.path.isfile(path):
            return
        root = ET.parse(path).getroot()
        for cu in root:
            if cu.tag != "CUnit":
                continue
            uid = cu.get("id")
            if uid is None:
                continue
            unit = self._unit(uid)
            if cu.get("parent"):
                unit["parent"] = cu.get("parent")

            # scalar fields. `Mob` and `HotkeyCategory` mark a real, player-controllable unit
            # (map doodads/destructibles like light bridges carry neither), so we track their
            # presence to flag playable units downstream.
            for child in cu:
                if child.tag in ("SubgroupAlias", "Race", "HotkeyCategory",
                                 "SubgroupPriority", "Mob") and child.get("value") is not None:
                    unit["fields"][child.tag] = child.get("value")

            # Card layouts. SC2's CardLayouts is a *positional* array: a card's identity is its
            # array index, and CardId is a property submenu buttons use to target it. A base mod
            # declares cards in document order (main page, then the CardId sub-cards); a later mod
            # patches one by `index`, often WITHOUT repeating the CardId -- e.g. voidmulti's
            # `<CardLayouts index="1">` reworks the Probe's PBl1 "Warp In Structure" sub-card. Keying
            # by CardId-or-index alone would split that patch into a phantom `@1` card holding the
            # sub-card's structures; instead we resolve index<->CardId to one canonical card via the
            # per-unit position map (an existing card at that slot wins, else CardId names it).
            pos_map = unit["card_pos"]
            for card in cu.findall("./CardLayouts"):
                pos = card_position(card, pos_map)
                ckey = pos_map.get(pos) or card.get("CardId") or ("@" + str(pos))
                pos_map[pos] = ckey
                if card.get("removed") == "1":
                    unit["cards"].pop(ckey, None)
                    for p in [p for p, k in pos_map.items() if k == ckey]:
                        del pos_map[p]
                    continue
                self._apply_card(unit, ckey, card)

    def _apply_card(self, unit, ckey, card):
        # SC2's LayoutButtons is an indexed array. A button with an explicit `index` patches that
        # slot; a button without one takes the next free slot (the running max index + 1, advanced
        # past explicit indices too). Later mods overwrite same-index slots; `removed="1"` clears
        # one. This reproduces cross-mod patches (e.g. voidmulti's index=4 ResearchSmartServos
        # replacing an older Factory Tech Lab research).
        #
        # But a *dependency* mod re-declaring a button that already exists is the SAME array
        # element, not a new one -- so a non-indexed button whose full identity (Face, AbilCmd)
        # already sits in the card reuses that slot instead of drifting to max+1. Without this, a
        # button re-stated non-indexed by two mods lands on two different slots, and a later
        # explicit-index override (which targets the single real slot) removes only one copy,
        # leaking a stale button (e.g. Infested Terran, cut from the LotV Infestor, survived on the
        # burrowed card). Identity is (Face, AbilCmd), NOT Face alone: a card legitimately carries
        # two same-Face buttons with different AbilCmds (e.g. a Factory's two distinct Cancels), and
        # collapsing those would shift every later slot and make voidmulti's index overrides miss.
        # Genuine same-Face/different-AbilCmd repeats (BurrowDown x12) still collapse later in
        # dedup_faces() for display.
        slots = unit["cards"].setdefault(ckey, {})
        next_idx = (max(slots) + 1) if slots else 0
        ident_slot = {}   # (Face, AbilCmd) -> slot, for reusing a re-declared identical button
        for i in sorted(slots):
            a = slots[i]
            if a.get("Face") or a.get("AbilCmd"):
                ident_slot.setdefault((a.get("Face"), a.get("AbilCmd")), i)
        for button in card.findall("./LayoutButtons"):
            attrs = child_attrs(button)
            bidx = attrs.get("index")
            if bidx is not None:
                bidx = int(bidx)
            else:
                ident = (attrs.get("Face"), attrs.get("AbilCmd"))
                bidx = ident_slot[ident] if ((ident[0] or ident[1]) and ident in ident_slot) else next_idx
            next_idx = max(next_idx, bidx + 1)
            # A `removed="1"` patch, or an explicit `Type="Undefined"` blank (SC2's idiom for
            # emptying a card cell), clears the slot. Drop its identity from ident_slot too, so a
            # later non-indexed restatement of that same button appends to a fresh slot rather than
            # silently reusing the just-emptied one. That reuse is what put Larva's Corruptor and
            # Infestor morphs on one grid cell: swarm blanks slot 7 (liberty's Corruptor) then
            # re-adds Corruptor non-indexed -- it must land on a new slot so voidmulti's index=11
            # column patch shifts it clear of Infestor instead of missing it.
            if attrs.get("removed") == "1" or (attrs.get("Type") == "Undefined" and not attrs.get("Face")):
                slots.pop(bidx, None)
                for k in [key for key, si in ident_slot.items() if si == bidx]:
                    del ident_slot[k]
                continue
            slots[bidx] = merge_button_attrs(slots.get(bidx, {}), attrs)
            a = slots[bidx]
            if a.get("Face") or a.get("AbilCmd"):
                ident_slot.setdefault((a.get("Face"), a.get("AbilCmd")), bidx)

    # -- parent inheritance ------------------------------------------------
    def resolve_parents(self):
        """Fold each unit's `parent` template beneath its own definition."""
        resolved = {}

        def resolve(uid, stack):
            if uid in resolved:
                return resolved[uid]
            unit = self.units.get(uid)
            if unit is None:
                return None
            pid = unit["parent"]
            base_cards, base_fields = {}, {}
            if pid and pid != uid and pid not in stack:
                parent = resolve(pid, stack | {uid})
                if parent:
                    base_cards = deepcopy(parent["cards"])
                    base_fields = dict(parent["fields"])
            merged_fields = dict(base_fields)
            merged_fields.update(unit["fields"])
            merged_cards = base_cards
            for cidx, slots in unit["cards"].items():
                tgt = merged_cards.setdefault(cidx, {})
                for bidx, attrs in slots.items():
                    tgt[bidx] = attrs
            out = {"fields": merged_fields, "cards": merged_cards}
            resolved[uid] = out
            return out

        for uid in list(self.units.keys()):
            resolve(uid, frozenset())
        self.units = resolved


def load_unitcatalog():
    cat = UnitCatalog()
    for mod in MP_CHAIN:
        cat.apply_mod(unitdata_path(mod))
    cat.resolve_parents()
    return cat


# --------------------------------------------------------------------------- assembly
def grid_position(attrs):
    """Return (row, col) for a button; default to (0,0) when unspecified."""
    row = attrs.get("Row")
    col = attrs.get("Column")
    return (int(row) if row is not None else 0,
            int(col) if col is not None else 0)


def display_name(command, strings):
    return (strings.get("Button/Name/" + command)
            or strings.get("Unit/Name/" + command)
            or command)


# Morph/transform states (Flying, Burrowed, sieged, ...) have no GameString of their own -- they
# reuse the base unit's name, annotated with the state: CommandCenterFlying -> "Command Center
# (Flying)".  Add-ons read the other way round (the add-on is the primary noun): BarracksTechLab ->
# "Tech Lab (Barracks)".  Longest suffixes first so "SiegeMode" wins over a bare "Mode", etc.
STATE_SUFFIXES = (
    ("SiegeMode", "Siege Mode"), ("Sieged", "Sieged"), ("Uprooted", "Uprooted"),
    ("Burrowed", "Burrowed"), ("Flying", "Flying"), ("Lowered", "Lowered"),
)
ADDON_SUFFIXES = (
    ("TechLab", "Tech Lab"), ("Reactor", "Reactor"),
)


def unit_display_name(uid, strings):
    exact = strings.get("Unit/Name/" + uid) or strings.get("Button/Name/" + uid)
    if exact:
        return exact
    # No string for this exact id: it's usually a morph/add-on variant of a base unit that has one.
    # Resolve the base name (recursively, e.g. LurkerMPBurrowed -> LurkerMP -> "Lurker") and annotate.
    for suf, addon in ADDON_SUFFIXES:
        if uid.endswith(suf) and len(uid) > len(suf):
            return "%s (%s)" % (addon, unit_display_name(uid[:-len(suf)], strings))
    for suf, state in STATE_SUFFIXES:
        if uid.endswith(suf) and len(uid) > len(suf):
            return "%s (%s)" % (unit_display_name(uid[:-len(suf)], strings), state)
    return uid


RACE_NAMES = {"Terr": "Terran", "Prot": "Protoss", "Zerg": "Zerg"}


def race_name(code):
    if not code:
        return None
    return RACE_NAMES.get(code, code)


# Generic commands every unit/building carries (movement, cancel, rally, construction) -- their
# presence doesn't make a unit a ladder unit, so they're excluded from the melee test below.
GENERIC_COMMANDS = frozenset([
    "Move", "Stop", "MoveHoldPosition", "MovePatrol", "Attack", "AttackWorker", "AttackRedirect",
    "AttackStructure", "AttackBuilding", "AcquireMove", "Cancel", "Halt", "CancelBuilding",
    "SelectBuilder", "Spray", "Rally", "ProgressRally", "SetRallyPoint", "SetWorkerRallyPoint",
    "SetUnitRallyPoint", "Taunt",
])


# A unit whose id is a melee unit's id plus one of these transform-state suffixes is the same unit
# in another form (a lifted building, sieged Thor, burrowed Ultralisk) and carries the toggle-back
# hotkey (Land / ExplosiveMode / Unburrow).  Deliberately NOT "MP" (QueenMP is the separate SC1
# Queen) or "Cocoon" (a morph egg with no real hotkeys).
TRANSFORM_SUFFIXES = ("Flying", "SiegeMode", "Sieged", "Uprooted", "Burrowed", "AP", "Lowered")


def base_unit_id(uid):
    for suf in TRANSFORM_SUFFIXES:
        if uid.endswith(suf) and len(uid) > len(suf):
            return uid[:-len(suf)]
    return uid


def load_melee():
    """The jcfieldsdev ladder roster (data/sc2_melee.json, from gen_sc2_melee.js): melee unit
    display-names and caster-ids. None if absent -- the melee flag then defaults to True."""
    path = os.path.join(HERE, "sc2_melee.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return {"names": set(d.get("unitNames", [])), "qualifiers": set(d.get("qualifiers", [])),
            "commands": set(d.get("commands", [])), "types": d.get("types", {})}


def build():
    hotkeys = load_gamehotkeys()
    strings = load_strings()
    buttons = load_buttondata()
    catalog = load_unitcatalog()
    melee = load_melee()

    units_out = {}
    defaults = {}  # "command[/unit]" -> key   (for validation)

    # Buttons that aren't rebindable commands: passive upgrade indicators (e.g. the "HaveSmartServos"
    # icon shown on units that benefit but don't research it) and hidden/unreachable buttons.
    SKIP_TYPES = ("Passive", "Undefined")

    for uid, unit in catalog.units.items():
        if not unit["cards"]:
            continue
        if "test" in uid.lower():
            continue  # internal debug units (AutoTest*, ScopeTest, TestZerg)
        qualifier = unit["fields"].get("SubgroupAlias", uid)
        race = race_name(unit["fields"].get("Race"))

        # A sub-card (CardId) is named by the sub-menu button that opens it (SubmenuCardId), so the
        # build sub-cards read "Build Structure" / "Build Advanced Structure" etc.
        submenu_label = {}
        for slots in unit["cards"].values():
            for attrs in slots.values():
                sub = attrs.get("SubmenuCardId")
                if sub and attrs.get("Face"):
                    submenu_label[sub] = display_name(resolve_command(attrs["Face"], buttons), strings)

        # A unit is a ladder (melee) unit if jcfieldsdev's curated roster lists it -- by caster id
        # (its own id or SubgroupAlias hosts melee commands, incl. add-ons like FactoryTechLab), by
        # display name (covers ability-less units like Archon/Colossus that own no command), or if
        # it owns a specific melee command (keeps state-variants like a flying building's Land).
        if melee is None:
            is_melee = True
        else:
            is_melee = (uid in melee["qualifiers"] or qualifier in melee["qualifiers"]
                        or unit_display_name(uid, strings) in melee["names"]
                        or base_unit_id(uid) in melee["qualifiers"])   # transform-state variant

        unit_cards = []
        has_move = False
        for ckey in sort_card_keys(unit["cards"].keys()):
            slots = unit["cards"][ckey]
            card_buttons = []
            for attrs in dedup_faces(slots):
                if attrs.get("Type") in SKIP_TYPES:
                    continue
                face = attrs.get("Face")
                command = resolve_command(face, buttons)
                if command == "Move":
                    has_move = True
                brec = buttons.get(command, {})
                universal = bool(brec.get("universal"))
                key = hotkeys.get(command, "")
                row, col = grid_position(attrs)
                out_name = command if universal else command + "/" + qualifier
                if key:
                    defaults.setdefault(out_name, key)
                # Only a UNIT-SPECIFIC (non-universal) melee command qualifies a unit -- universal
                # commands (Burrow, Stim, ...) are shared and would leak SC1 remakes like the Defiler
                # (which has Burrow) into the ladder set.
                if (melee is not None and not is_melee and not universal
                        and command not in GENERIC_COMMANDS and out_name in melee["commands"]):
                    is_melee = True
                card_buttons.append({
                    "face": face,
                    "command": command,
                    "name": display_name(command, strings),
                    "key": key,
                    "row": row,
                    "col": col,
                    "universal": universal,
                    "type": attrs.get("Type"),
                    "submenu": attrs.get("SubmenuCardId"),
                    "icon": brec.get("icon"),
                })
            if card_buttons:
                label = "" if ckey.startswith("@") else submenu_label.get(ckey, "Submenu")
                unit_cards.append({"id": ckey, "label": label, "buttons": card_buttons})
        if unit_cards:
            fields = unit["fields"]
            # `Mob`/`HotkeyCategory` mark a real, controllable unit (doodads carry neither). But a
            # later mod blanking `HotkeyCategory` to "" *decommissions* the unit from the hotkey UI
            # -- how voidmulti removed the Mothership Core in LotV 3.0 -- even though a stale `Mob`
            # lingers from an earlier mod. So an explicitly-empty HotkeyCategory means not playable.
            hc = fields.get("HotkeyCategory")
            playable = hc != "" and (("HotkeyCategory" in fields) or ("Mob" in fields))
            # unit vs building: jcfieldsdev's type (by name / caster id / base id), else mobility
            # (a unit with a Move command is mobile -> a unit; otherwise a structure).
            types = melee["types"] if melee else {}
            uname = unit_display_name(uid, strings)
            kind = (types.get(uname) or types.get(uid) or types.get(qualifier)
                    or types.get(base_unit_id(uid)) or ("unit" if has_move else "building"))
            units_out[uid] = {
                "id": uid,
                "name": uname,
                "qualifier": qualifier,
                "race": race,
                "playable": playable,
                "melee": is_melee,
                "kind": kind,
                "cards": unit_cards,
            }

    return units_out, defaults


def main():
    units_out, defaults = build()

    out_json = os.path.join(HERE, "sc2.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump({"units": units_out}, fh, indent=1, ensure_ascii=False, sort_keys=True)

    out_ini = os.path.join(HERE, "sc2_defaults.ini")
    with open(out_ini, "w", encoding="utf-8") as fh:
        for line in sorted(defaults):
            fh.write("%s=%s\n" % (line, defaults[line]))

    print("units with cards : %d" % len(units_out))
    print("default bindings : %d" % len(defaults))
    print("wrote %s" % os.path.relpath(out_json, HERE))
    print("wrote %s" % os.path.relpath(out_ini, HERE))


if __name__ == "__main__":
    main()
