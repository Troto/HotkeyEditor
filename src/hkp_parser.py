#!/usr/bin/python
"""Parser for AoE2: Definitive Edition hotkey files (.hkp).

Core entry/compression logic based on crimsoncantab/aok-hotkeys
(modules/hkparse.py, modules/hkizip.py):
  - file is raw-deflate compressed (zlib, -MAX_WBITS)
  - a hotkey entry is 12 bytes: '<Ii???x'
    (key code, string id, ctrl, alt, shift, 1 pad byte)

DE stores two kinds of .hkp per profile, each in two format versions:

ProfileName.hkp ("shared" hotkeys, the legacy 9 hki-style menus):
  v4.20: float32 version | uint32 num_menus | menus | empty menu slots
         (trailing uint32 zero-counts)
  v4.32: float32 version | uint32 num_menus | "baseHotkeysBegin"
         "sharedHotkeyGroupsBegin" | menus | "sharedHotkeyGroupsEnd"
         "baseHotkeysEnd"

ProfileName/Base.hkp ("additional" hotkeys, the new remappable system):
  v4.20: float32 version | unit menu | game menu | cycle menu |
         uint32 num_groups | groups (uint32 count + entries each)
  v4.32: same data wrapped in sentinels:
         "additionalHotkeysBegin"
         "allUnitCommandHotkeysBegin" menu "allUnitCommandHotkeysEnd"
         "allGameCommandHotkeysBegin" menu "allGameCommandHotkeysEnd"
         "allCycleCommandHotkeysBegin" menu "allCycleCommandHotkeysEnd"
         "detachedHotkeyGroupsBegin" uint32 num_groups |
            per group: uint32 count "detachedHotkeysGroupBegin"
                       entries "detachedHotkeysGroupEnd"
         "detachedHotkeyGroupsEnd" "additionalHotkeysEnd"

A "menu" is uint32 count + entries.  In v4.32 every entry is wrapped:
  "HandlerBaseGroupBegin" uint32 0x00100a60 "GroupHeaderGuard"
  <12-byte entry> "HandlerBaseGroupEnd"
"""
import json
import struct
import sys
import zlib

HEADER_FORMAT = struct.Struct('<f')
COUNT_FORMAT = struct.Struct('<I')
HOTKEY_FORMAT = struct.Struct('<Ii4B')  # code, string id, ctrl, alt, shift, pad

GROUP_HEADER_MAGIC = 0x00100a60

S_BASE_BEGIN = b'baseHotkeysBegin'
S_BASE_END = b'baseHotkeysEnd'
S_SHARED_BEGIN = b'sharedHotkeyGroupsBegin'
S_SHARED_END = b'sharedHotkeyGroupsEnd'
S_HANDLER_BEGIN = b'HandlerBaseGroupBegin'
S_HANDLER_END = b'HandlerBaseGroupEnd'
S_GUARD = b'GroupHeaderGuard'
S_ADDITIONAL_BEGIN = b'additionalHotkeysBegin'
S_ADDITIONAL_END = b'additionalHotkeysEnd'
S_SECTIONS = [(b'allUnitCommandHotkeysBegin', b'allUnitCommandHotkeysEnd'),
              (b'allGameCommandHotkeysBegin', b'allGameCommandHotkeysEnd'),
              (b'allCycleCommandHotkeysBegin', b'allCycleCommandHotkeysEnd')]
S_DETACHED_BEGIN = b'detachedHotkeyGroupsBegin'
S_DETACHED_END = b'detachedHotkeyGroupsEnd'
S_DGROUP_BEGIN = b'detachedHotkeysGroupBegin'
S_DGROUP_END = b'detachedHotkeysGroupEnd'


def decompress(data):
    d = zlib.decompressobj(-zlib.MAX_WBITS)
    return d.decompress(data) + d.flush()


def compress(data):
    c = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED,
                         -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL,
                         zlib.Z_DEFAULT_STRATEGY)
    return c.compress(data) + c.flush()


class ParseError(Exception):
    pass


class Reader(object):
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def u32(self):
        (v,) = COUNT_FORMAT.unpack_from(self.data, self.pos)
        self.pos += 4
        return v

    def f32(self):
        (v,) = HEADER_FORMAT.unpack_from(self.data, self.pos)
        self.pos += 4
        return v

    def peek(self, literal):
        return self.data[self.pos:self.pos + len(literal)] == literal

    def lit(self, literal):
        if not self.peek(literal):
            raise ParseError('expected %r at offset %d' % (literal, self.pos))
        self.pos += len(literal)

    def entry(self):
        code, sid, ctrl, alt, shift, pad = HOTKEY_FORMAT.unpack_from(
            self.data, self.pos)
        self.pos += HOTKEY_FORMAT.size
        return {'code': code, 'id': sid,
                'ctrl': ctrl, 'alt': alt, 'shift': shift, 'pad': pad}

    def wrapped_entry(self):
        self.lit(S_HANDLER_BEGIN)
        if self.u32() != GROUP_HEADER_MAGIC:
            raise ParseError('bad group header magic at %d' % (self.pos - 4))
        self.lit(S_GUARD)
        e = self.entry()
        self.lit(S_HANDLER_END)
        return e

    def menu(self, wrapped):
        count = self.u32()
        if count > 100000:
            raise ParseError('implausible count %d at %d'
                             % (count, self.pos - 4))
        read = self.wrapped_entry if wrapped else self.entry
        return [read() for _ in range(count)]

    def eof(self):
        return self.pos == len(self.data)


def parse_shared(r, wrapped):
    num_menus = r.u32()
    if wrapped:
        r.lit(S_BASE_BEGIN)
        r.lit(S_SHARED_BEGIN)
    menus = [r.menu(wrapped) for _ in range(num_menus)]
    empty_slots = 0
    if wrapped:
        while not r.peek(S_SHARED_END):
            if r.u32() != 0:
                raise ParseError('expected empty menu slot at %d'
                                 % (r.pos - 4))
            empty_slots += 1
        r.lit(S_SHARED_END)
        r.lit(S_BASE_END)
    else:
        while not r.eof():
            if r.u32() != 0:
                raise ParseError('expected empty menu slot at %d'
                                 % (r.pos - 4))
            empty_slots += 1
    return {'kind': 'shared', 'menus': menus, 'empty_slots': empty_slots}


def parse_base(r, wrapped):
    sections = []
    if wrapped:
        r.lit(S_ADDITIONAL_BEGIN)
        for begin, end in S_SECTIONS:
            r.lit(begin)
            sections.append(r.menu(wrapped=True))
            r.lit(end)
        r.lit(S_DETACHED_BEGIN)
    else:
        for _ in S_SECTIONS:
            sections.append(r.menu(wrapped=False))
    num_groups = r.u32()
    groups = []
    for _ in range(num_groups):
        if wrapped:
            count = r.u32()
            r.lit(S_DGROUP_BEGIN)
            groups.append([r.wrapped_entry() for _ in range(count)])
            r.lit(S_DGROUP_END)
        else:
            groups.append(r.menu(wrapped=False))
    if wrapped:
        r.lit(S_DETACHED_END)
        r.lit(S_ADDITIONAL_END)
    return {'kind': 'base',
            'unit_commands': sections[0],
            'game_commands': sections[1],
            'cycle_commands': sections[2],
            'detached_groups': groups}


def parse(data):
    """Parse decompressed .hkp data; detects layout and version."""
    r = Reader(data)
    version = r.f32()
    if r.peek(S_ADDITIONAL_BEGIN):
        info = parse_base(r, wrapped=True)
    elif data[8:8 + len(S_BASE_BEGIN)] == S_BASE_BEGIN:
        info = parse_shared(r, wrapped=True)
    else:
        # plain binary (v4.20): try shared layout first, then base
        for fn in (parse_shared, parse_base):
            r = Reader(data)
            r.f32()
            try:
                info = fn(r, wrapped=False)
                break
            except (ParseError, struct.error):
                info = None
        if info is None:
            raise ParseError('unrecognized .hkp layout')
    if not r.eof():
        raise ParseError('trailing data at offset %d of %d'
                         % (r.pos, len(r.data)))
    info['version'] = round(version, 2)
    info['wrapped'] = version >= 4.25
    return info


def parse_file(path):
    with open(path, 'rb') as f:
        return parse(decompress(f.read()))


# --- writing -----------------------------------------------------------

def _write_entry(out, e, wrapped):
    raw = HOTKEY_FORMAT.pack(e['code'], e['id'], e['ctrl'], e['alt'],
                             e['shift'], e.get('pad', 0))
    if wrapped:
        out.append(S_HANDLER_BEGIN)
        out.append(COUNT_FORMAT.pack(GROUP_HEADER_MAGIC))
        out.append(S_GUARD)
        out.append(raw)
        out.append(S_HANDLER_END)
    else:
        out.append(raw)


def _write_menu(out, menu, wrapped):
    out.append(COUNT_FORMAT.pack(len(menu)))
    for e in menu:
        _write_entry(out, e, wrapped)


def unparse(info):
    """Rebuild decompressed .hkp bytes from a parse() result."""
    wrapped = info['wrapped']
    out = [HEADER_FORMAT.pack(info['version'])]
    if info['kind'] == 'shared':
        out.append(COUNT_FORMAT.pack(len(info['menus'])))
        if wrapped:
            out.append(S_BASE_BEGIN)
            out.append(S_SHARED_BEGIN)
        for menu in info['menus']:
            _write_menu(out, menu, wrapped)
        out.append(COUNT_FORMAT.pack(0) * info['empty_slots'])
        if wrapped:
            out.append(S_SHARED_END)
            out.append(S_BASE_END)
    else:
        sections = [info['unit_commands'], info['game_commands'],
                    info['cycle_commands']]
        if wrapped:
            out.append(S_ADDITIONAL_BEGIN)
            for (begin, end), menu in zip(S_SECTIONS, sections):
                out.append(begin)
                _write_menu(out, menu, wrapped=True)
                out.append(end)
            out.append(S_DETACHED_BEGIN)
            out.append(COUNT_FORMAT.pack(len(info['detached_groups'])))
            for group in info['detached_groups']:
                out.append(COUNT_FORMAT.pack(len(group)))
                out.append(S_DGROUP_BEGIN)
                for e in group:
                    _write_entry(out, e, wrapped=True)
                out.append(S_DGROUP_END)
            out.append(S_DETACHED_END)
            out.append(S_ADDITIONAL_END)
        else:
            for menu in sections:
                _write_menu(out, menu, wrapped=False)
            out.append(COUNT_FORMAT.pack(len(info['detached_groups'])))
            for group in info['detached_groups']:
                _write_menu(out, group, wrapped=False)
    return b''.join(out)


def write_file(path, info):
    with open(path, 'wb') as f:
        f.write(compress(unparse(info)))


# --- CLI ---------------------------------------------------------------

def summarize(path):
    with open(path, 'rb') as f:
        data = decompress(f.read())
    info = parse(data)
    roundtrip = 'ok' if unparse(info) == data else 'MISMATCH'
    if info['kind'] == 'shared':
        shape = '%d menus %s + %d empty slots' % (
            len(info['menus']), [len(m) for m in info['menus']],
            info['empty_slots'])
    else:
        shape = 'unit=%d game=%d cycle=%d, %d detached groups %s' % (
            len(info['unit_commands']), len(info['game_commands']),
            len(info['cycle_commands']), len(info['detached_groups']),
            [len(g) for g in info['detached_groups']])
    print('%s\n  version %.2f %s, %s\n  round-trip: %s'
          % (path, info['version'], info['kind'], shape, roundtrip))
    return info


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--json']
    as_json = '--json' in sys.argv
    for path in args:
        if as_json:
            print(json.dumps(parse_file(path), indent=2))
        else:
            summarize(path)
