# Hotkey Editor

A local, self-contained web app for viewing/editing game **hotkey profiles**, with an
on-screen keyboard that visualises your binds while you edit. It runs entirely in the
browser: host the built folder on any static site, or just open the file locally. No
server, no install, no network.

The editor is **multi-game**: a shared UI/engine plus one **module per game** that knows
that game's file format, command data, and conflict rules. Each game builds to its own
self-contained page.

- **Currently supported:** Age of Empires II: DE — see **[games/aoe2/README.md](games/aoe2/README.md)**;
  Warcraft III (classic/Reforged `CustomKeys.txt`) — see **[games/Warcraft3/README.md](games/Warcraft3/README.md)**.

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
- **Command list** grouped into collapsible columns with a filter box. By default groups are
  ordered alphabetically and balanced across columns; a game may instead supply an order
  (`groupKey`) and strict per-category columns (`groupCategory`, see below).
- **Category filter buttons** (when a game supplies `filters`) — e.g. WC3's race buttons; a
  single-select bar that narrows the list, composing with the search box. Absent for AoE2.
- **Strict category columns** (when a game supplies `groupCategory`) — instead of one balanced
  split across all groups, each category keeps its own whole columns (never mixed) and longer
  categories get proportionally more columns. Absent for AoE2 (keeps the balanced split).
- **Start from bundled defaults** (when a game provides them) — a one-click button loads a
  built-in default file, so you can begin editing without picking your own file first.
- **Conflict framework:** the engine pairs up every two commands that share the exact combo
  (key + ctrl/alt/shift) and asks the active game module to classify them into three tiers —
  **confirmed** (red ⚠), **possible** (amber ⚐), **override** (blue ⓘ) — shown as key rings,
  row markers, and a toolbar badge that filters the list to flagged commands. The *rules* are
  the game's; the pairing, display, and tiers are the engine's.

## Module architecture (adding a game)

A game module supplies, behind a small interface:

- **codec** — owns the file(s) entirely. The engine holds one **opaque per-game document**
  (`state.doc`) and never inspects it; the codec defines its shape. Two async methods:
  `load(file, prevDoc) → doc` (decode one picked file and merge it into the doc — so a game can
  take one file or several, text or binary, in any order) and `save(doc, name) →
  { blob, filename, note? }` (package the download — `.zip`, `.txt`, anything). AoE2 is a
  compressed binary `.hkp` pair zipped together; other games (e.g. WC3) are a single plain-text
  file. The engine assumes nothing about the format. Optionally a codec may also expose
  `loadDefault(prevDoc) → doc` to build a doc from a **bundled default file** (the module inlines
  the file text via its dataset); when present alongside `meta.defaultsLabel`, the shell shows a
  one-click "load defaults" button so a user can start without picking a file.
- **bindings / forEachEntry** — `bindings(doc) → [rec]` turns the doc into the engine's editable
  records; `forEachEntry(doc, fn)` iterates the raw entries (used by the Dvorak remap).
- **fileStatus** — `fileStatus(doc, name) → html` for the toolbar's load-status chips (the game
  decides what "loaded / still need to load" looks like).
- **dataset** — the inlined data: command id → name, display grouping, and conflict context.
  (For AoE2, the `--regen` output: `strings`/`card_data`/`civ_data`.)
- **conflict ruleset** — `classify(a, b) → confirmed | possible | override | null` for two
  commands sharing a combo.
- **list order & filtering (all optional)** — a game may refine how the command list is laid out:
  `groupKey(rec) → sortStr` sets the group/column order (default: alphabetical by group name);
  `groupCategory(rec) → id` turns on strict per-category columns (categories never share a column,
  longer ones get more columns); `filters → [{id,label}]` (+ `meta.filterLabel`) renders the
  filter-button bar and `recFilters(rec) → [id]` decides which buttons a record belongs to. A game
  that defines none of these gets the plain balanced, alphabetical, unfiltered list (e.g. AoE2).
- **input** — game-specific input bits only: extra mouse buttons and any extra VK labels.
  (Dvorak / keyboard layouts are engine-level, **not** per game.)
- **meta** — display name, file label/accept, load/save help copy, and flags
  (`multiple`, `usesProfileName`, `hasChroniclesToggle`, and optional `defaultsLabel` for the
  "load defaults" button, …). The engine's `applyMeta()` paints this copy into the shell so
  `page.html` carries no game-specific text.

The engine reaches all of this through `GAME.*` (the active entry in the `GAMES` registry).
A game's `module.js` defines its implementations and registers itself via
`GAMES.<slug> = { … }`; `--build` injects that file into the shell at the
`/* __GAME_MODULE__ */` marker, and the active game is chosen from the inlined
`window.GAME_DATA.game` tag.

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
