#!/usr/bin/env python3
"""Convert the StarCraft II ability icons referenced by sc2.json from DDS to PNG.

Browsers can't render .dds, so we decode the (uncompressed / DXT1 / DXT5) DDS
textures with a small pure-stdlib decoder and re-encode them as PNG via zlib.

Outputs:
  data/icons/<dds-basename>.png   one PNG per unique icon actually used
  data/sc2_icons.json             command id -> "icons/<file>.png"

Python 3.7 stdlib only (struct, zlib).
"""

import glob
import json
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_SRC = os.path.join(HERE, "SC2 data", "Icons", "mods")
LINK_FILE = os.path.join(HERE, "SC2 data", "SC2 texture ability link.txt")
OUT_DIR = os.path.join(HERE, "icons")


# --------------------------------------------------------------------------- DDS decode
def _rgb565(c):
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _dxt_colors(c0, c1, dxt1):
    (r0, g0, b0), (r1, g1, b1) = _rgb565(c0), _rgb565(c1)
    colors = [(r0, g0, b0, 255), (r1, g1, b1, 255)]
    if c0 > c1 or not dxt1:
        colors.append(((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255))
        colors.append(((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255))
    else:  # 3-colour block with transparency (DXT1 only)
        colors.append(((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255))
        colors.append((0, 0, 0, 0))
    return colors


def _decode_block_colors(data, off, dxt1, out, x0, y0, w, h, alpha=None):
    c0, c1 = struct.unpack_from("<HH", data, off)
    bits = struct.unpack_from("<I", data, off + 4)[0]
    colors = _dxt_colors(c0, c1, dxt1)
    for py in range(4):
        for px in range(4):
            idx = (bits >> (2 * (4 * py + px))) & 0x3
            r, g, b, a = colors[idx]
            if alpha is not None:
                a = alpha[4 * py + px]
            x, y = x0 + px, y0 + py
            if x < w and y < h:
                p = (y * w + x) * 4
                out[p:p + 4] = bytes((r, g, b, a))


def _decode_dxt5_alpha(data, off):
    a0, a1 = data[off], data[off + 1]
    if a0 > a1:
        pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        pal = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    bits = int.from_bytes(data[off + 2:off + 8], "little")
    return [pal[(bits >> (3 * i)) & 0x7] for i in range(16)]


def decode_dds(path):
    """Return (width, height, RGBA bytes)."""
    data = open(path, "rb").read()
    if data[:4] != b"DDS ":
        raise ValueError("not a DDS: %s" % path)
    h, w = struct.unpack_from("<II", data, 12)
    pf_flags, fourcc = struct.unpack_from("<I4s", data, 80)
    rgb_bits = struct.unpack_from("<I", data, 88)[0]
    masks = struct.unpack_from("<IIII", data, 92)  # R,G,B,A
    off = 128
    out = bytearray(w * h * 4)

    if pf_flags & 0x4:  # DDPF_FOURCC -> compressed
        dxt1 = fourcc == b"DXT1"
        block_bytes = 8 if dxt1 else 16
        for by in range(0, h, 4):
            for bx in range(0, w, 4):
                if dxt1:
                    _decode_block_colors(data, off, True, out, bx, by, w, h)
                else:  # DXT5: 8 bytes alpha + 8 bytes colour
                    alpha = _decode_dxt5_alpha(data, off)
                    _decode_block_colors(data, off + 8, False, out, bx, by, w, h, alpha)
                off += block_bytes
        return w, h, bytes(out)

    # uncompressed, masked (24 or 32 bit)
    rmask, gmask, bmask, amask = masks

    def shift(m):
        if not m:
            return 0, 0
        s = 0
        while not (m >> s) & 1:
            s += 1
        return s, m >> s

    rs, rmax = shift(rmask)
    gs, gmax = shift(gmask)
    bs, bmax = shift(bmask)
    as_, amax = shift(amask)
    nbytes = rgb_bits // 8
    for i in range(w * h):
        px = int.from_bytes(data[off + i * nbytes: off + i * nbytes + nbytes], "little")
        r = ((px & rmask) >> rs) if rmask else 0
        g = ((px & gmask) >> gs) if gmask else 0
        b = ((px & bmask) >> bs) if bmask else 0
        a = ((px & amask) >> as_) if amask else 255
        out[i * 4: i * 4 + 4] = bytes((r, g, b, a))
    return w, h, bytes(out)


# --------------------------------------------------------------------------- PNG encode
def write_png(path, w, h, rgba):
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0
        raw += rgba[y * w * 4:(y + 1) * w * 4]
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


# --------------------------------------------------------------------------- driver
def index_textures():
    return {os.path.basename(p).lower(): p
            for p in glob.glob(os.path.join(ICON_SRC, "*", "base.sc2assets",
                                            "assets", "textures", "*.dds"))}


def load_link_fallback():
    """display-name -> dds basename, from the editor-exported link file."""
    out = {}
    if not os.path.isfile(LINK_FILE):
        return out
    with open(LINK_FILE, encoding="utf-8-sig") as fh:
        rows = [line.rstrip("\n").split("\t") for line in fh]
    if len(rows) < 2:
        return out
    for name, path in zip(rows[0][1:], rows[1][1:]):
        if name and path:
            out[name.strip()] = path.replace("\\", "/").split("/")[-1].lower()
    return out


def dds_basename(icon_path):
    return icon_path.replace("\\", "/").split("/")[-1].lower()


def main():
    units = json.load(open(os.path.join(HERE, "sc2.json"), encoding="utf-8"))["units"]
    textures = index_textures()
    link = load_link_fallback()

    # command -> dds basename (buttondata icon, else link file by display name)
    want = {}
    for u in units.values():
        for card in u["cards"]:
            for b in card["buttons"]:
                cmd = b["command"]
                if cmd in want:
                    continue
                fn = dds_basename(b["icon"]) if b.get("icon") else None
                if not fn or fn not in textures:
                    fn = link.get(b["name"])
                if fn and fn in textures:
                    want[cmd] = fn

    os.makedirs(OUT_DIR, exist_ok=True)
    icon_map = {}
    converted = {}
    fails = []
    for cmd, fn in sorted(want.items()):
        png_name = os.path.splitext(fn)[0] + ".png"
        if fn not in converted:
            try:
                w, h, rgba = decode_dds(textures[fn])
                write_png(os.path.join(OUT_DIR, png_name), w, h, rgba)
                converted[fn] = png_name
            except Exception as exc:  # noqa: BLE001
                fails.append((cmd, fn, str(exc)))
                continue
        icon_map[cmd] = "icons/" + png_name

    with open(os.path.join(HERE, "sc2_icons.json"), "w", encoding="utf-8") as fh:
        json.dump(icon_map, fh, indent=1, ensure_ascii=False, sort_keys=True)

    total_cmds = len({b["command"] for u in units.values()
                      for c in u["cards"] for b in c["buttons"]})
    print("commands total     : %d" % total_cmds)
    print("icons matched       : %d" % len(icon_map))
    print("unique PNGs written : %d" % len(converted))
    if fails:
        print("FAILED (%d):" % len(fails))
        for cmd, fn, err in fails[:10]:
            print("  %s (%s): %s" % (cmd, fn, err))


if __name__ == "__main__":
    main()
