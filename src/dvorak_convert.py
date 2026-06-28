#!/usr/bin/python
"""Convert an AoE2:DE hotkey profile between QWERTY and Dvorak layouts.

Hotkey files store Windows virtual-key codes, which follow the characters
of the active OS keyboard layout rather than physical key positions.  To
keep hotkeys on the same physical keys after switching the OS layout to
Dvorak, every key code is replaced with the code the same physical key
reports under Dvorak (e.g. the physical QWERTY 'Q' key types ' on Dvorak,
so hotkey Q becomes VK_OEM_7).  Keys whose position doesn't change
(A, M, digits, F-keys, numpad, arrows, ...) pass through untouched.

Converts the full profile pair the game requires:
    <Name>.hkp  and  <Name>/Base.hkp

Usage:
    python dvorak_convert.py "path/to/Profile.hkp" ["New Name"]
        [--reverse] [--dry-run] [--force]
"""
import argparse
import os
import sys

import hkp_parser

# physical keys whose typed character differs between QWERTY and Dvorak:
# (character on the key under QWERTY, character under Dvorak)
LAYOUT_CHANGES = [
    ('-', '['), ('=', ']'),
    ('q', "'"), ('w', ','), ('e', '.'), ('r', 'p'), ('t', 'y'),
    ('y', 'f'), ('u', 'g'), ('i', 'c'), ('o', 'r'), ('p', 'l'),
    ('[', '/'), (']', '='),
    ('s', 'o'), ('d', 'e'), ('f', 'u'), ('g', 'i'), ('h', 'd'),
    ('j', 'h'), ('k', 't'), ('l', 'n'), (';', 's'), ("'", '-'),
    ('z', ';'), ('x', 'q'), ('c', 'j'), ('v', 'k'), ('b', 'x'),
    ('n', 'b'), (',', 'w'), ('.', 'v'), ('/', 'z'),
]

# virtual-key code for each character (US layout VK assignments)
CHAR_TO_VK = {
    "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF, ';': 0xBA,
    '[': 0xDB, ']': 0xDD, '-': 0xBD, '=': 0xBB, '\\': 0xDC, '`': 0xC0,
}
for _c in 'abcdefghijklmnopqrstuvwxyz0123456789':
    CHAR_TO_VK[_c] = ord(_c.upper())
VK_TO_CHAR = dict((v, k) for k, v in CHAR_TO_VK.items())

# the changed keys must be a permutation of the same physical key set
assert (sorted(c for c, _ in LAYOUT_CHANGES)
        == sorted(c for _, c in LAYOUT_CHANGES))


def build_vk_map(reverse=False):
    vk_map = {}
    for qwerty, dvorak in LAYOUT_CHANGES:
        src, dst = (dvorak, qwerty) if reverse else (qwerty, dvorak)
        vk_map[CHAR_TO_VK[src]] = CHAR_TO_VK[dst]
    return vk_map


def key_name(code):
    if code in VK_TO_CHAR:
        return VK_TO_CHAR[code].upper()
    return 'VK_%d' % code


def all_menus(info):
    if info['kind'] == 'shared':
        return list(info['menus'])
    return ([info['unit_commands'], info['game_commands'],
             info['cycle_commands']] + list(info['detached_groups']))


def convert_info(info, vk_map, stats):
    for menu in all_menus(info):
        for entry in menu:
            stats['total'] += 1
            new_code = vk_map.get(entry['code'])
            if new_code is not None:
                pair = (entry['code'], new_code)
                stats['changes'][pair] = stats['changes'].get(pair, 0) + 1
                entry['code'] = new_code
                stats['changed'] += 1


def profile_paths(top_path):
    base_dir = os.path.splitext(top_path)[0]
    return top_path, os.path.join(base_dir, 'Base.hkp')


def main():
    ap = argparse.ArgumentParser(
        description='Convert an AoE2:DE hotkey profile QWERTY <-> Dvorak '
                    '(keeps hotkeys on the same physical keys).')
    ap.add_argument('source', help="path to the profile's top-level .hkp")
    ap.add_argument('dest', nargs='?',
                    help='new profile name or .hkp path '
                         '(default: "<source> Dvorak")')
    ap.add_argument('--reverse', action='store_true',
                    help='convert Dvorak -> QWERTY instead')
    ap.add_argument('--dry-run', action='store_true',
                    help='report changes without writing files')
    ap.add_argument('--force', action='store_true',
                    help='overwrite the destination if it exists')
    args = ap.parse_args()

    src_top, src_base = profile_paths(args.source)
    for p in (src_top, src_base):
        if not os.path.isfile(p):
            sys.exit('error: missing %s (a profile needs both the named '
                     '.hkp and <name>/Base.hkp)' % p)

    suffix = ' QWERTY' if args.reverse else ' Dvorak'
    if args.dest:
        dest = args.dest if args.dest.lower().endswith('.hkp') \
            else args.dest + '.hkp'
        if not os.path.dirname(dest):
            dest = os.path.join(os.path.dirname(src_top), dest)
    else:
        base = os.path.splitext(src_top)[0]
        old_suffix = ' Dvorak' if args.reverse else ' QWERTY'
        if base.endswith(old_suffix):
            base = base[:-len(old_suffix)]
        dest = base + suffix + '.hkp'
    dst_top, dst_base = profile_paths(dest)
    if dst_top == src_top:
        sys.exit('error: destination equals source')

    vk_map = build_vk_map(args.reverse)
    stats = {'total': 0, 'changed': 0, 'changes': {}}
    shared = hkp_parser.parse_file(src_top)
    base = hkp_parser.parse_file(src_base)
    convert_info(shared, vk_map, stats)
    convert_info(base, vk_map, stats)

    direction = 'Dvorak -> QWERTY' if args.reverse else 'QWERTY -> Dvorak'
    print('%s: %d hotkeys, %d remapped (%s)'
          % (args.source, stats['total'], stats['changed'], direction))
    for (old, new), n in sorted(stats['changes'].items(),
                                key=lambda kv: -kv[1]):
        print('  %-3s -> %-3s  x%d' % (key_name(old), key_name(new), n))

    if args.dry_run:
        print('dry run: nothing written')
        return
    if not args.force and (os.path.exists(dst_top)
                           or os.path.exists(dst_base)):
        sys.exit('error: %s already exists (use --force to overwrite)'
                 % dst_top)
    dst_dir = os.path.dirname(dst_base)
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
    hkp_parser.write_file(dst_top, shared)
    hkp_parser.write_file(dst_base, base)
    print('wrote %s' % dst_top)
    print('wrote %s' % dst_base)


if __name__ == '__main__':
    main()
