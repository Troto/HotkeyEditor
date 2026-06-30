# Hotkey Editor

A local, self-contained web app for viewing/editing game **hotkey profiles**, with an
on-screen keyboard that visualises your binds while you edit. It runs entirely in the
browser: host the built folder on any static site, or just open the file locally. No
server, no install, no network.

The editor is **multi-game**: a shared UI/engine plus one **module per game** that knows
that game's file format, command data, and conflict rules. Each game builds to its own
self-contained page.

- **Currently supported:** Age of Empires II: DE — see **[games/aoe2/README.md](games/aoe2/README.md)**.

## How it runs

- **`page.html`** is the shared **UI shell / engine** (HTML/CSS/JS, no framework). It renders
  the keyboard, the command list, highlighting/search, the QWERTY⇄Dvorak toggle, and the
  conflict display — none of which are game-specific.
- Each game has a **generator** under `games/<game>/` that produces that game's data and
  **inlines it (and the game's `module.js`) into the shell** (via the shared `page_assembler`)
  to emit a self-contained `site/<game>/index.html`.
- **`site/index.html`** is a small **launcher** that links to every built game.

Open a built `site/<game>/index.html` directly (offline) or serve `site/` from any static
host. The data is baked in, so there are no runtime fetches or game-install dependencies.

## Build

```
python3 build.py                                       # build every game + the launcher
```

`build.py` discovers `games/*/`, builds each `site/<game>/index.html`, and writes the combined
launcher. To rebuild a single game while iterating, run its generator directly (it also
refreshes the launcher across all built games):

```
python3 games/aoe2/game_module_generator.py --build    # -> site/aoe2/index.html
```

To preview: build, then `python3 -m http.server 8765` and open
http://localhost:8765/site/aoe2/index.html (or `site/index.html` for the launcher).

## Files

- **`build.py`** — the all-games build entry point: discovers `games/*/`, builds each, and
  writes the combined launcher (a thin wrapper over `page_assembler.build_all`).
- **`page.html`** — the shared UI shell / engine. Edit this for anything generic (keyboard,
  list, Dvorak, conflict display). **Don't** edit the built `site/**/index.html` (generated).
- **`page_assembler.py`** — shared, game-agnostic helper: inlines a game's data **and its
  `module.js`** into `page.html` to write `site/<game>/index.html`, emits the
  `site/index.html` launcher, and orchestrates the all-games build (`discover_games`/
  `build_all`).
- **`games/<game>/`** — one folder per game module: its build/data CLI, its `module.js`
  (file-format codec + naming/grouping + conflict rules, wired into the engine via `GAME.*`),
  its file-format parser/oracle, and its vendored data. See the per-game README (e.g.
  [games/aoe2/](games/aoe2/README.md)).
- **`site/`** — the deployable output: the launcher plus one `site/<game>/index.html` per game.
- **`Example Key files/`** — sample profiles for testing (currently AoE2).

## Generic engine features

- **On-screen keyboard + mouse**, shaded by how many commands are bound to each key (toggle).
  Click a command → highlight its key; hover → lighter preview; click a key → list its
  commands; click a group heading → highlight the whole group.
- **Rebind** by left-clicking a key button then pressing a key (or clicking a key on the
  visual); right-click to unbind.
- **QWERTY⇄Dvorak** slide toggle — converts binds *and* relabels the keyboard. This is
  **game-agnostic**: a bind is a virtual-key code, and remapping VK codes between layouts is
  independent of the game (a load is interpreted as the current toggle position).
- **Command list** grouped into collapsible, balanced alphabetical columns, with a filter box.
- **Conflict framework:** the engine pairs up every two commands that share the exact combo
  (key + ctrl/alt/shift) and asks the active game module to classify them into three tiers —
  **confirmed** (red ⚠), **possible** (amber ⚐), **override** (blue ⓘ) — shown as key rings,
  row markers, and a toolbar badge that filters the list to flagged commands. The *rules* are
  the game's; the pairing, display, and tiers are the engine's.

## Module architecture (adding a game)

A game module supplies, behind a small interface:

- **codec** — load the uploaded file(s) into an editable set of bindings, and serialize back to
  a downloadable file. This is fully game-owned: AoE2 is a compressed binary `.hkp` packaged as
  a zip; other games (e.g. SC2/WC3) are plain-text INI files. The engine assumes nothing about
  the format.
- **dataset** — the inlined data: command id → name, display grouping, and conflict context.
  (For AoE2, the `--regen` output: `strings`/`card_data`/`civ_data`.)
- **conflict ruleset** — `classify(a, b) → confirmed | possible | override | null` for two
  commands sharing a combo.
- **input** — game-specific input bits only: extra mouse buttons and any extra VK labels.
  (Dvorak / keyboard layouts are engine-level, **not** per game.)
- **meta** — display name, file extension/accept, load/save help text, optional toggles.

The engine reaches all of this through `GAME.*` (the active entry in the `GAMES` registry).
A game's `module.js` defines its implementations and wires them up via
`Object.assign(GAMES.<slug>, { … })`; `--build` injects that file into the shell at the
`/* __GAME_MODULE__ */` marker.

> **Status:** the per-game split is in place. `page.html` is the generic engine/UI shell and
> calls game code only through `GAME.*`; all AoE2-specific logic (the `.hkp` codec, naming/
> grouping, and conflict rules) lives in [`games/aoe2/module.js`](games/aoe2/module.js),
> injected at build. Adding a second game means adding `games/<game>/` with its own
> `module.js` + generator. See [games/aoe2/README.md](games/aoe2/README.md) for the AoE2
> specifics.

## Gotchas (generic)

- Build/data tooling targets **Python 3.7**, **stdlib only** (no walrus, no `bytes.hex(sep)`).
- Firefox/Gecko reports different keyCodes for `; = -` (59/61/173); the engine normalises them
  via `GECKO`.
- A game's file-format parser must round-trip **byte-exact**; verify after any change (AoE2 has
  a Python oracle + a JS port that are checked against each other).
