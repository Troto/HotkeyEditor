#!/usr/bin/python
"""Shared page-assembly helpers for the per-game module generators.

The editor's UI lives in one shell, page.html.  Each game has its own generator
(e.g. games/aoe2/game_module_generator.py) that produces that game's data, then
calls assemble() here to inline the data into the shell and write the
self-contained site/<game>/index.html.  write_launcher() emits the small
site/index.html that links to every built game.

build_all() is the all-games entry point (see the root build.py): it discovers
games/<slug>/game_module_generator.py, builds each, and writes the combined
launcher.  A game's generator must expose `build() -> (slug, name) | None` and a
module-level `_GAME_NAME`.

This file is game-agnostic on purpose -- no AoE2 (or any one game's) specifics
belong here.  Stdlib only (Python 3.7).
"""
import importlib.util
import json
import os

# The shell's injection points.  --build replaces each whole marker line: the data
# marker swaps the `null` placeholder for a `{ game, data }` payload, and the module
# marker is replaced by the game's module.js -- so the built page is self-contained.
DATA_MARKER = 'window.GAME_DATA = null; /* __GAME_DATA__ */'
DATA_VAR = 'window.GAME_DATA'
MODULE_MARKER = '/* __GAME_MODULE__ */'


def assemble(page_path, data, out_path, module_js=None, game=None):
    """Inline `data` (and, if given, `module_js`) into the page.html shell.

    The data is wrapped as `{ "game": game, "data": data }` so the page knows which
    registered game module to activate.  Writes a self-contained html and returns the
    byte length written.  Raises if the shell or a required marker is missing.  The json
    is compacted and any "</..." is neutralised so an embedded string can't close the
    <script> tag early; module_js is trusted game code and is injected verbatim (it must
    not contain a literal "</script>").
    """
    if not os.path.isfile(page_path):
        raise RuntimeError('page shell not found: %s' % page_path)
    page = open(page_path, encoding='utf-8').read()
    if DATA_MARKER not in page:
        raise RuntimeError('data marker not found in %s' % page_path)
    payload = {'game': game, 'data': data}
    blob = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = page.replace(DATA_MARKER, '%s = %s; /* __GAME_DATA__ */' % (DATA_VAR, blob))
    if module_js is not None:
        if MODULE_MARKER not in out:
            raise RuntimeError('module marker not found in %s' % page_path)
        if '</script>' in module_js:
            raise RuntimeError('module_js contains "</script>"; would close the tag early')
        out = out.replace(MODULE_MARKER, module_js)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(out)
    return len(out.encode('utf-8'))


def write_launcher(site_dir, games):
    """Write site/index.html: a minimal landing page linking to each built game.

    `games` is a list of (slug, display_name); each is expected at
    site/<slug>/index.html.  Game-agnostic; safe to call with a single game.
    """
    items = '\n'.join(
        '    <li><a href="./%s/index.html">%s</a></li>' % (slug, _esc(name))
        for slug, name in games)
    html = _LAUNCHER_TEMPLATE % {'items': items}
    os.makedirs(site_dir, exist_ok=True)
    out_path = os.path.join(site_dir, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path


def _esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def discover_games(root):
    """Import every games/<slug>/game_module_generator.py under `root`.

    Returns a list of (slug, name, module) sorted by slug.  `slug` is the folder
    name (authoritative); `name` is the module's _GAME_NAME (falling back to slug).
    Importing a generator only defines its functions -- build()/regen() run only
    under `if __name__ == '__main__'`, so discovery has no side effects.
    """
    games_dir = os.path.join(root, 'games')
    found = []
    if not os.path.isdir(games_dir):
        return found
    for slug in sorted(os.listdir(games_dir)):
        gen_path = os.path.join(games_dir, slug, 'game_module_generator.py')
        if not os.path.isfile(gen_path):
            continue
        spec = importlib.util.spec_from_file_location('game_module_%s' % slug, gen_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found.append((slug, getattr(mod, '_GAME_NAME', slug), mod))
    return found


def build_all(root):
    """Build every discovered game's page, then write the combined launcher.

    Returns the list of (slug, name) successfully built.  THE all-games command
    (root build.py is a thin wrapper around this).
    """
    built = []
    for slug, name, mod in discover_games(root):
        if mod.build():                       # (slug, name) on success, None on failure
            built.append((slug, name))
        else:
            print('skipped %s (build failed)' % slug)
    write_launcher(os.path.join(root, 'site'), built)
    print('wrote site/index.html (launcher: %s)' % (', '.join(s for s, _ in built) or 'none'))
    return built


def write_launcher_for_built(root):
    """Refresh site/index.html to list every game that already has a built page.

    Lets a single game's `--build` keep the launcher complete (listing the other
    games too) without rebuilding them.  Returns the (slug, name) list written.
    """
    site_dir = os.path.join(root, 'site')
    games = [(slug, name) for slug, name, _ in discover_games(root)
             if os.path.isfile(os.path.join(site_dir, slug, 'index.html'))]
    write_launcher(site_dir, games)
    return games


_LAUNCHER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hotkey Editor</title>
<style>
  body { font-family: system-ui, sans-serif; background:#1c1c1e; color:#eee;
         margin:0; display:flex; min-height:100vh; align-items:center; justify-content:center; }
  .card { text-align:center; }
  h1 { font-weight:600; }
  ul { list-style:none; padding:0; }
  li { margin:.5rem 0; }
  a { display:inline-block; padding:.6rem 1.4rem; border-radius:8px;
      background:#2c2c2e; color:#7fd; text-decoration:none; min-width:12rem; }
  a:hover { background:#3a3a3c; }
</style>
</head>
<body>
  <div class="card">
    <h1>Hotkey Editor</h1>
    <p>Choose a game:</p>
    <ul>
%(items)s
    </ul>
  </div>
</body>
</html>
"""
