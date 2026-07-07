#!/usr/bin/python
"""Extract official AoE2:DE command icons and map them to hotkey command ids.

Unlike the rest of the runtime data, this reads a **game install** (like `--regen`): it needs the
uncompressed icon textures and the civ tech-tree json the game ships.  Point it at an install with
`AOE2_INSTALL=/path/to/.../AoE2DE` (the folder holding `widgetui/` and `resources/`).  Its outputs --
`aoe2_icons.json` (`{command id -> icon basename}`) and the regenerated `icons/*.png` -- are committed,
so the app build and runtime never need the install.

How the mapping is data-driven (no fuzzy wiki filenames, no binary .dat parsing):
  * The game's `resources/_common/dat/CivTechTrees/*.json` (generated from the .dat) list every
    unit / building / tech node with its canonical `Name` and a `Picture Index` -- the exact index
    into the icon texture folders `widgetui/textures/ingame/{buildings,units,tech}/NNN_*.DDS`.
  * We build a canonical **name -> official icon** table from those nodes (choosing the modal icon
    per name so civ variants don't win over the base icon), then match each carded hotkey command to
    it by NAME: the command's display name (`strings.json`) contains the unit/building/tech noun
    (verb-stripped -- "Select all Markets" -> "Markets" -> depluralised "Market").  `OVERRIDES`
    (by id) and `NAME_OVERRIDES` (by command name) pin the rest (the unit-selectors: idle villager,
    trade carts, wonders...).

The icon textures are uncompressed 32-bit RGBA DDS (256x256, no mipmaps); we decode them and
box-downscale to 128x128 PNG with stdlib only (zlib + struct) -- no third-party deps.  Only icons a
command actually references are emitted.  Commands with no unit/building/tech icon (control groups,
stances, Attack Move, Buy/Sell, campaign units) simply get none -- the overlay skips them.

Usage: AOE2_INSTALL=/path/to/AoE2DE python3 gen_aoe2_icons.py
"""
import collections
import glob
import json
import os
import re
import shutil
import struct
import zlib

_HERE = os.path.dirname(os.path.abspath(__file__))

# Where to find a game install (holds widgetui/ + resources/).  Env override, else a couple of
# common spots; this is a regen-time dependency only -- the committed outputs need no install.
_INSTALL_CANDIDATES = [
    os.environ.get('AOE2_INSTALL'),
    os.path.join(_HERE, 'install files', 'AoE2DE'),
    '/mnt/c/Program Files (x86)/Steam/steamapps/common/AoE2DE',
]

TARGET_PX = 128                       # downscale icons to this square size

# id -> icon basename to force a specific match; '' means "no icon" (suppress a bad fuzzy match).
OVERRIDES = {
    '419114': '',      # "Tech: Artillery Spotters" -- Paphos-campaign only, not a real unit; don't
                       #   match it to the "Artillery" node.
}

# command display-name -> canonical node Name to borrow the icon from.  Used where the command names
# no single unit/building (the selection-group commands) but a representative icon reads well.
NAME_OVERRIDES = {
    # selection-group commands that name no single unit -> a representative unit/building icon
    'Select all Idle Villagers': 'Villager',
    'Go to Idle Villager': 'Villager',
    'Go to Next Idle Villager': 'Villager',
    'Select all Trade Carts/Cogs': 'Trade Cart',
    'Select all Idle Trade Carts/Cogs': 'Trade Cart',
    'Go to Trade Cart': 'Trade Cart',
    'Select all Wonders and Monuments': 'Wonder',
    # Blacksmith attack/armor UPGRADE-LINE commands -> the line's first-tier tech icon (the command
    # names the whole line, so match its representative tech).
    'Tech: Melee Attack Upgrades': 'Forging',
    'Tech: Arrow Attack Upgrades': 'Fletching',
    'Tech: Infantry Armor Upgrades': 'Scale Mail Armor',
    'Tech: Cavalry Armor Upgrades': 'Scale Barding Armor',
    'Tech: Archer Armor Upgrades': 'Padded Archer Armor',
    # economy upgrade-line commands -> first-tier tech icon
    'Tech: Gold Upgrades': 'Gold Mining',
    'Tech: Stone Upgrades': 'Stone Mining',
    'Tech: Wood Upgrades': 'Double-Bit Axe',
    # age advance -> the Feudal Age icon (one of the four age icons)
    'Tech: Age Up': 'Feudal Age',
    'Tech: Tower Upgrades': 'Watch Tower',
    'Tower': 'Watch Tower',                         # villager "Build Tower" command
}

# Command-action icons: these live in widgetui/textures/ingame/actions/NNN_.png (already PNG), but no
# data file maps a hotkey command to an action-icon index -- buttons.json exposes only a handful, and
# stance/formation buttons are hardcoded in game code.  So this is a hand-map (command name -> atlas
# index), identified visually from the atlas.  Confidence is noted per entry; the LOW/GUESS ones are
# best-effort and want review (see the printed report).  Edit freely; unmapped actions just show none.
ACTION_OVERRIDES = {
    # --- confirmed by buttons.json icon_id (extremely high confidence) ---
    'Set Gather Point': 45,
    'Set Gather Point on Self': 45,
    'Remove Gather Point': 46,
    'Ring Town Bell': 49,
    'Go Back to Work': 64,
    'Go Back to Work (Fortified Church, Dock)': 64,
    'All Back to Work': 64,                         # shares the back-to-work icon (78 has no atlas file)
    # --- military-unit command card, indices PIXEL-MATCHED against the user's ExampleCommandCard
    #     (each card cell cropped and matched to the atlas by lowest MSE -- objective, not guessed;
    #     see the card + scratchpad/match_card.py). Card layout: row1 patrol/guard/follow/attack-move/
    #     garrison, row2 stances, row3 formations. ---
    'Patrol': 6,
    'Guard': 7,
    'Follow': 8,
    'Attack Move': 41,
    'Garrison': 69,
    'Aggressive': 9,
    'Defensive': 10,
    'Stand Ground': 51,
    'No Attack': 50,
    'Stop': 3,
    'Line': 65,
    'Box': 43,
    'Staggered': 63,                                # the card's "scatter"
    'Flank': 62,
    # --- more command-action cards (Villager/Monk/Siege/Mill), pixel-matched against the user's
    #     ExampleCommandCards/ screenshots + standalone icon captures (autoscout, lock gate) ---
    'Auto Scout': 75,                               # compass (standalone screenshot)
    'Lock/Unlock Gate': 47,                         # gate (standalone screenshot)
    'Economic Buildings': 30,                       # villager build-menu (eco)
    'Military Buildings': 31,                       # villager build-menu (mil)
    'Convert': 14,
    'Heal': 15,
    'Drop Relic': 16,
    'Attack Ground': 60,                            # siege attack-ground (Mangonel/Trebuchet)
    'Pack': 12,
    'Unpack': 13,                                   # Packed Trebuchet -> unpack
    'Repair': 28,
    'Seek Shelter': 88,
    'Unload': 17,                                   # transport-ship unload (boat)
    'Unload (Siege)': 42,                           # siege-tower unload (arrow over wall)
    'Ungarrison': 2,                                # universal ungarrison
    'Drop Off Resources': 87,                       # villager
    'Toggle Automatic Farm Reseeding': 70,          # Mill -> green farm toggle
    'Toggle Automatic Fish Trap Rebuilding': 72,    # green fish-trap toggle (Fish Trap + Port cards)
    # (indices for Pack/Repair/Seek Shelter/Unload/Ungarrison/Drop Relic read from the atlas by the
    #  user; the card-cell crops were too noisy to pixel-match those reliably)
    # --- Market buy/sell: the plain commodity icon (the game overlays "buy"/"sell" text at runtime,
    #     so the icon itself is just the resource) ---
    'Buy 100 Food': 19, 'Sell 100 Food': 19,       # 19 = raw meat (food)
    'Buy 100 Wood': 18, 'Sell 100 Wood': 18,       # 18 = wood logs
    'Buy 100 Stone': 21, 'Sell 100 Stone': 21,     # 21 = stone cube
}

# command name -> (folder, picture index) for icons pulled straight from a texture folder that the
# CivTechTree doesn't reference.  E.g. the market trade-ratio icons live in tech/ (094_wood_trading_0x
# ...) but aren't tech-tree nodes, so name-matching never finds them.
FOLDER_ICON_OVERRIDES = {
    'Trade 0% Wood':   ('tech', 94),                # wood_trading_0x  (all gold)
    'Trade 50% Wood':  ('tech', 157),               # wood_trading_1x
    'Trade 100% Wood': ('tech', 95),                # wood_trading_4x  (all wood)
}

# Node types -> which icon texture folder their Picture Index indexes into.
_FOLDER = {
    'BuildingTech': 'buildings', 'BuildingNonTech': 'buildings',
    'RegionalBuilding': 'buildings', 'UniqueBuilding': 'buildings',
    'Unit': 'units', 'UnitUpgrade': 'units', 'RegionalUnit': 'units', 'UniqueUnit': 'units',
    'Research': 'tech',
}
_FOLDER_PRIO = {'buildings': 0, 'units': 1, 'tech': 2}   # prefer a building icon over a tech of same name


# ---------------------------------------------------------------------------- DDS -> PNG (stdlib)

def _load_dds_rgba(path):
    """Return (width, height, rgba_bytes) for a DDS icon (RGBA32, DXT1/BC1, or DXT5/BC3)."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'DDS ':
        raise ValueError('not a DDS: %s' % path)
    height, width = struct.unpack('<2I', data[12:20])
    fourcc = data[84:88]
    bitcount = struct.unpack('<I', data[88:92])[0]
    body = data[128:]                                     # first surface (no mipmaps in these icons)
    if fourcc == b'DXT1':
        return width, height, _decode_bc(body, width, height, dxt5=False)
    if fourcc == b'DXT5':
        return width, height, _decode_bc(body, width, height, dxt5=True)
    if fourcc == b'\x00\x00\x00\x00' and bitcount == 32:
        pixels = body[:width * height * 4]
        masks = struct.unpack('<4I', data[92:108])        # R,G,B,A bit masks
        if masks == (0xff, 0xff00, 0xff0000, 0xff000000):  # already R,G,B,A byte order
            return width, height, pixels
        shifts = [_mask_shift(m) for m in masks]           # generic swizzle (e.g. BGRA)
        out = bytearray(len(pixels))
        for i in range(0, len(pixels), 4):
            px = struct.unpack('<I', pixels[i:i + 4])[0]
            for c, (sh, mask) in enumerate(zip(shifts, masks)):
                out[i + c] = (px & mask) >> sh
        return width, height, bytes(out)
    raise ValueError('unexpected DDS format (fourcc=%r bpp=%d) in %s' % (fourcc, bitcount, path))


def _mask_shift(mask):
    return ((mask & -mask).bit_length() - 1) if mask else 0


def _rgb565(c):
    r = (c >> 11) & 0x1f
    g = (c >> 5) & 0x3f
    b = c & 0x1f
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _decode_bc(body, width, height, dxt5):
    """Decode BC1 (DXT1) / BC3 (DXT5) block texture to R,G,B,A bytes (top-down)."""
    out = bytearray(width * height * 4)
    block = 16 if dxt5 else 8
    bx = (width + 3) // 4
    pos = 0
    for by in range((height + 3) // 4):
        for bxi in range(bx):
            blk = body[pos:pos + block]
            pos += block
            if dxt5:
                a0, a1 = blk[0], blk[1]
                abits = int.from_bytes(blk[2:8], 'little')
                if a0 > a1:
                    alpha = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
                else:
                    alpha = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
                cblk = blk[8:16]
            else:
                cblk = blk
            c0, c1 = struct.unpack('<2H', cblk[0:4])
            r0, g0, b0 = _rgb565(c0)
            r1, g1, b1 = _rgb565(c1)
            colors = [(r0, g0, b0, 255), (r1, g1, b1, 255)]
            if c0 > c1 or dxt5:
                colors.append(((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255))
                colors.append(((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255))
            else:
                colors.append(((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255))
                colors.append((0, 0, 0, 0))               # BC1 1-bit transparency
            cbits = struct.unpack('<I', cblk[4:8])[0]
            for py in range(4):
                y = by * 4 + py
                if y >= height:
                    break
                for px in range(4):
                    x = bxi * 4 + px
                    if x >= width:
                        continue
                    idx = (cbits >> (2 * (4 * py + px))) & 3
                    r, g, b, a = colors[idx]
                    if dxt5:
                        a = alpha[(abits >> (3 * (4 * py + px))) & 7]
                    o = (y * width + x) * 4
                    out[o] = r; out[o + 1] = g; out[o + 2] = b; out[o + 3] = a
    return bytes(out)


def _box_downscale(width, height, rgba, target):
    """Average-box downscale by an integer factor to ~target px (RGBA, no deps)."""
    factor = max(1, min(width // target, height // target))
    if factor == 1:
        return width, height, rgba
    nw, nh = width // factor, height // factor
    out = bytearray(nw * nh * 4)
    inv = 1.0 / (factor * factor)
    for y in range(nh):
        for x in range(nw):
            r = g = b = a = 0
            for dy in range(factor):
                row = ((y * factor + dy) * width + x * factor) * 4
                for dx in range(factor):
                    p = row + dx * 4
                    r += rgba[p]; g += rgba[p + 1]; b += rgba[p + 2]; a += rgba[p + 3]
            o = (y * nw + x) * 4
            out[o] = int(r * inv); out[o + 1] = int(g * inv)
            out[o + 2] = int(b * inv); out[o + 3] = int(a * inv)
    return nw, nh, bytes(out)


def _write_png(path, width, height, rgba):
    """Minimal RGBA PNG writer (stdlib zlib)."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)                                     # filter type 0 (None)
        raw += rgba[y * width * 4:(y + 1) * width * 4]

    def chunk(tag, payload):
        return (struct.pack('>I', len(payload)) + tag + payload
                + struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', ihdr))
        f.write(chunk(b'IDAT', zlib.compress(bytes(raw), 9)))
        f.write(chunk(b'IEND', b''))


def _dds_to_png(src, dst):
    w, h, rgba = _load_dds_rgba(src)
    w, h, rgba = _box_downscale(w, h, rgba, TARGET_PX)
    _write_png(dst, w, h, rgba)


# ---------------------------------------------------------------------------- name -> icon table

def _find_install():
    for c in _INSTALL_CANDIDATES:
        if c and os.path.isdir(os.path.join(c, 'widgetui', 'textures', 'ingame')):
            return c
    raise SystemExit('No AoE2DE install found. Set AOE2_INSTALL=/path/to/AoE2DE (needs widgetui/ + '
                     'resources/_common/dat/CivTechTrees/).')


def _icon_index(install):
    """folder -> {picture index -> source DDS path}, from widgetui/textures/ingame/<folder>/NNN_*."""
    idx = {}
    base = os.path.join(install, 'widgetui', 'textures', 'ingame')
    for folder in ('buildings', 'units', 'tech'):
        m = {}
        for f in os.listdir(os.path.join(base, folder)):
            g = re.match(r'(\d+)_.*\.dds$', f, re.I)
            if g:
                m[int(g.group(1))] = os.path.join(base, folder, f)
        idx[folder] = m
    return idx


def _name_table(install, icon_idx):
    """Canonical node Name -> (folder, source DDS path), one representative (modal) icon per name."""
    votes = collections.defaultdict(lambda: collections.Counter())   # name -> Counter[(folder, pidx)]
    for jf in glob.glob(os.path.join(install, 'resources', '_common', 'dat', 'CivTechTrees', '*.json')):
        d = json.load(open(jf, encoding='utf-8'))
        for key in ('civ_techs_buildings', 'civ_techs_units'):
            for n in d.get(key, []):
                name = n.get('Name')
                pidx = n.get('Picture Index')
                folder = _FOLDER.get(n.get('Node Type'))
                if name and pidx is not None and folder and pidx in icon_idx[folder]:
                    votes[name][(folder, pidx)] += 1
    table = {}
    for name, counter in votes.items():
        # pick by folder priority first, then most common index within that folder
        folder = min(set(f for (f, _) in counter), key=lambda f: _FOLDER_PRIO.get(f, 9))
        (bf, bp), _ = max((kv for kv in counter.items() if kv[0][0] == folder),
                          key=lambda kv: (kv[1], -kv[0][1]))
        table[name] = (bf, icon_idx[bf][bp])
    return table


# ---------------------------------------------------------------------------- command matching

def _norm(s):
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def _deplural(word):
    for suf, rep in (('ies', 'y'), ('ches', 'ch'), ('shes', 'sh'), ('sses', 'ss'), ('s', '')):
        if word.lower().endswith(suf) and len(word) > len(suf) + 1:
            return word[:-len(suf)] + rep
    return word


def _candidates(name):
    """Ordered, de-duped normalised keys to try for a command name (most specific first)."""
    n = re.sub(r'\(.*?\)', '', name)                              # drop "(Campaign Only)" etc.
    # campaign card prefixes -> the underlying unit/tech name ("Scenario 16: War Galley" -> War Galley)
    n = re.sub(r"^\s*(Scenario \d+|Alexander's Army|Mercenary):\s*", '', n, flags=re.I)
    n = re.sub(r'^\s*Tech:\s*', '', n, flags=re.I).strip()
    base = re.sub(r'^(Select all|Go to|Build|Train|Rebuild|Reseed|Sell \d+|Buy \d+)\s+',
                  '', n, flags=re.I)
    out = []

    def add(text):
        k = _norm(text)
        if k and k not in out:
            out.append(k)

    for variant in (n, base):
        add(variant)
        add(re.sub(r'-line', '', variant, flags=re.I))
        add(' '.join(_deplural(w) for w in variant.split()))
    for seg in re.split(r'[,/]', base):                          # "Knight-line, Hei Guang" -> Knight
        seg = re.sub(r'-line', '', seg, flags=re.I).strip()
        add(seg)
        add(' '.join(_deplural(w) for w in seg.split()))
    add(base.strip().split(' ')[0] if base.strip() else '')      # first-word fallback
    return out


def _sanitize(name):
    return re.sub(r'[^A-Za-z0-9]+', '', name)


def build():
    install = _find_install()
    icon_idx = _icon_index(install)
    table = _name_table(install, icon_idx)
    by_norm = {}                                                 # normalised name -> (folder, path)
    canon_by_norm = {}                                           # normalised name -> canonical Name
    for name, fp in table.items():
        k = _norm(name)
        if k and k not in by_norm:
            by_norm[k] = fp
            canon_by_norm[k] = name

    strings = json.load(open(os.path.join(_HERE, 'strings.json'), encoding='utf-8'))
    card = json.load(open(os.path.join(_HERE, 'card_data.json'), encoding='utf-8'))
    by_id = card['byId']

    # command id -> (canonical name, source DDS path)
    resolved = {}
    for cid, name in strings.items():
        if cid not in by_id:                                     # only carded commands get an icon slot
            continue
        if cid in OVERRIDES:
            key = _norm(OVERRIDES[cid]) if OVERRIDES[cid] else None
            if key and key in by_norm:
                resolved[cid] = (canon_by_norm[key], by_norm[key][1])
            continue
        if name in NAME_OVERRIDES:
            key = _norm(NAME_OVERRIDES[name])
            if key in by_norm:
                resolved[cid] = (canon_by_norm[key], by_norm[key][1])
            continue
        for k in _candidates(name):
            if k in by_norm:
                resolved[cid] = (canon_by_norm[k], by_norm[k][1])
                break

    # extract each referenced icon once, named by canonical node name; write aoe2_icons.json
    icons_dir = os.path.join(_HERE, 'icons')
    if os.path.isdir(icons_dir):
        for f in os.listdir(icons_dir):
            if f.endswith('.png'):
                os.remove(os.path.join(icons_dir, f))
    else:
        os.makedirs(icons_dir)

    src_for_base = {}                                            # basename -> (source path, is_action)
    out = {}
    for cid, (cname, src) in resolved.items():
        base = _sanitize(cname)
        src_for_base.setdefault(base, (src, False))
        out[cid] = base
    # command-action icons (hand-mapped to the actions/ atlas), for commands not already resolved
    actions_dir = os.path.join(install, 'widgetui', 'textures', 'ingame', 'actions')
    n_actions = 0
    for cid, name in strings.items():
        if cid in by_id and cid not in out and name in ACTION_OVERRIDES:
            idx = ACTION_OVERRIDES[name]
            src = os.path.join(actions_dir, '%03d_.png' % idx)
            if not os.path.exists(src):
                print('WARNING: action icon %03d for %r not in atlas; skipped' % (idx, name))
                continue
            base = 'act%03d' % idx
            src_for_base.setdefault(base, (src, True))
            out[cid] = base
            n_actions += 1
    # icons pulled straight from a texture folder by index (DDS), for UI icons the tech-tree omits
    n_folder = 0
    for cid, name in strings.items():
        if cid in by_id and cid not in out and name in FOLDER_ICON_OVERRIDES:
            folder, fidx = FOLDER_ICON_OVERRIDES[name]
            src = icon_idx.get(folder, {}).get(fidx)
            if not src:
                print('WARNING: %s icon %d for %r not found; skipped' % (folder, fidx, name))
                continue
            base = '%s%03d' % (folder, fidx)
            src_for_base.setdefault(base, (src, False))         # DDS -> decode
            out[cid] = base
            n_folder += 1
    for base, (src, is_action) in sorted(src_for_base.items()):
        dst = os.path.join(icons_dir, base + '.png')
        if is_action:
            shutil.copyfile(src, dst)                            # already PNG
        else:
            _dds_to_png(src, dst)

    ordered = {cid: out[cid] for cid in sorted(out, key=lambda x: int(x) if x.isdigit() else x)}
    path = os.path.join(_HERE, 'aoe2_icons.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(ordered, f, separators=(',', ':'), ensure_ascii=False)
        f.write('\n')

    carded = sum(1 for cid in strings if cid in by_id)
    print('install: %s' % install)
    print('wrote %s (%d/%d carded commands matched, %d unique icons @ %dpx; %d via action atlas)'
          % (os.path.relpath(path, _HERE), len(ordered), carded, len(src_for_base), TARGET_PX,
             n_actions))


if __name__ == '__main__':
    build()
