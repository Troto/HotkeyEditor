#!/usr/bin/python
"""Warcraft III game module generator -- static-site build for the hotkey editor.

WC3 hotkeys are a single plain-text CustomKeys.txt.  --build inlines the repo-root page.html
shell + this game's module.js + the vendored dataset (data/wc3.json: ability/unit names,
command-card groupings and the per-card conflict model, derived from jcfieldsdev's editor --
see data/SOURCE.md) to produce site/warcraft3/index.html.  There is no --regen: the dataset is
static (no game-install dependency); refresh it with data/gen_wc3_data.js if upstream changes.

Note the source folder is `games/Warcraft3/` (capitalised) but the slug -- and therefore the
`site/<slug>/` folder -- is lowercase `warcraft3`.

Stdlib only (works on Python 3.7).
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))            # games/Warcraft3/
_ROOT = os.path.dirname(os.path.dirname(_HERE))               # repo root
_GAME_SLUG = 'warcraft3'                                      # lowercase site/ slug
_GAME_NAME = 'Warcraft III'

sys.path.insert(0, _ROOT)                                     # for the shared page_assembler
import page_assembler                                         # noqa: E402


def build():
    """Assemble the self-contained site/warcraft3/index.html from page.html + module.js + data.

    Inlines data/wc3.json (names/grouping/conflict tables) plus the bundled "good defaults" file
    (so the page offers a one-click default load) for the module's setData.  Returns (slug, name)
    on success or None on failure -- the page_assembler.build_all contract.
    """
    page_path = os.path.join(_ROOT, 'page.html')
    module_path = os.path.join(_HERE, 'module.js')
    data_path = os.path.join(_HERE, 'data', 'wc3.json')
    names_path = os.path.join(_HERE, 'data', 'wc3_names.json')
    defaults_path = os.path.join(_HERE, 'HotkeyFiles', 'Sensible Reforged CustomKeys.txt')
    try:
        module_js = open(module_path, encoding='utf-8').read()
        with open(data_path, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError as e:
        print('ERROR: missing %s' % e.filename)
        return None
    try:
        with open(names_path, encoding='utf-8') as f:
            data['names'] = json.load(f)       # SLK-derived code->name, for Miscellaneous labels
    except FileNotFoundError:
        print('WARNING: %s missing; Miscellaneous commands fall back to file comments/raw codes'
              % os.path.basename(names_path))
    try:
        # newline='' so the file's original CRLF survives (no universal-newline translation),
        # keeping the bundled defaults byte-for-byte identical to the source file.
        with open(defaults_path, encoding='utf-8', newline='') as f:
            data['defaults'] = f.read()       # bundled into GAME_DATA -> module setData -> loadDefault
    except FileNotFoundError:
        print('WARNING: %s missing; "load defaults" button will be hidden' % os.path.basename(defaults_path))
    out_path = os.path.join(_ROOT, 'site', _GAME_SLUG, 'index.html')
    try:
        nbytes = page_assembler.assemble(page_path, data, out_path, module_js, _GAME_SLUG)
    except RuntimeError as e:
        print('ERROR: %s' % e)
        return None
    print('wrote site/%s/index.html (%d KB)' % (_GAME_SLUG, nbytes // 1024))
    return (_GAME_SLUG, _GAME_NAME)


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--build' in args or not args:
        if build() is None:
            sys.exit(1)
        page_assembler.write_launcher_for_built(_ROOT)
        print('wrote site/index.html (launcher)')
        sys.exit(0)
    print(__doc__)
