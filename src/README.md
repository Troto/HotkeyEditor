# Hotkey Editor

A local, self-contained web app for viewing/editing game **hotkey profiles**, with an
on-screen keyboard that visualises your binds while you edit. It runs entirely in the
browser: host the built folder on any static site, or just open the file locally. No
server, no install, no network.

The editor is **multi-game**: a shared UI/engine plus one **module per game** that knows
that game's file format, command data, and conflict rules. Each game builds to its own
self-contained page.

- **Currently supported:** Age of Empires II: DE — see **[games/aoe2/README.md](games/aoe2/README.md)**;
  Warcraft III (classic/Reforged `CustomKeys.txt`) — see **[games/Warcraft3/README.md](games/Warcraft3/README.md)**;
  StarCraft II (LotV multiplayer `.SC2Hotkeys`) — see **[games/Starcraft2/README.md](games/Starcraft2/README.md)**.

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
  commands; click a group heading → highlight the whole group. When the game supplies `icon`,
  selecting a card (or **hovering** a command row or a group heading) also overlays each of that
  card's ability icons on the keys they're bound to — the selected card persists, a hover is a
  temporary preview that reverts on mouse-out (see below).
- **Auto-sized keyboard region.** The sticky header (`#kbwrap`) is a three-column
  `.kbstage` grid: a capped-width left column (`.kbside`), the centred keyboard (`.kb`), and
  the command-card panel (`.cardpanel`). The left column stacks, top-to-bottom: the checkbox
  options (`.kbtools`, laid out side by side — shade, show instructions, show Chronicles, and
  **show numpad / show nav keys**, both off by default so the `.kbsec-num` / `.kbsec-nav` blocks
  start hidden and the rest of the keyboard scales up larger), the **hide-conflicts** option
  (`.conflicttools`), the **conflict panel** — which
  is `flex: 1 1 0; min-height` so it fills the leftover height and *scrolls its own overflow*,
  keeping a long conflict list from growing the sticky header and pushing the command list
  offscreen (the fixed rows keep their natural height) — and below it the list tools
  (collapse/expand with the filter box inline to their right) and the category filter when a game
  supplies `filters` (e.g. WC3 races). Nothing is stacked above or below the keyboard, so the
  keyboard and command card (both vertically centred in the row) own the full vertical space.
  `fitKeyboard()` then scales the keyboard to fill it: every key/gap/card-slot dimension is a
  `calc()` on the CSS vars `--ku` (key unit) / `--kg` (gap) on `#kbwrap`, so it measures the
  keyboard at the 34px reference and sets `--ku` to the largest value (clamped 26–54px) that fits
  both the available height (viewport minus header, less a reserve for the list) and the centre
  column's width. The keyboard carries a little top/bottom padding for breathing room, and the
  command-card slots are sized by a separate `--cu` — a modest size, shrunk only so up to two cards
  (command + hero learn) still fit side by side in the right gutter; the card is a small grid
  centred in its space (not stretched to the keyboard's height), with the slot key label a corner
  badge that scales with `--cu`. The mouse visual
  rides a dampened `--mscale` (half the keyboard's growth rate — a modest sidekick, not a rival),
  and is omitted entirely for games with no bindable mouse buttons (e.g. WC3). Runs on load,
  resize, layout (QWERTY⇄Dvorak) re-render, the show-numpad/nav toggles, and instructions-band
  toggle. The `34px`/`4px`/`1` fallbacks keep the help-panel sample keys (outside `#kbwrap`) at
  original size.
- **Rebind** by left-clicking a key button then pressing a key (or clicking a key on the
  visual); right-click to unbind. The same rebind capture can be started from a **command-card
  slot** — click a filled slot and it prompts "press a key…" just like the list-row button.
- **Reposition on the command card** (opt-in per game via `GAME.setSlot`) — drag a slot to an
  empty slot to move that command, or onto a filled slot to swap the two; the module writes the
  new position back to the file (WC3's `Buttonpos`). A slot shared by more than one command shows a
  conflict ring **only** when two of them genuinely clash per the game's conflict rules (ring colored
  by severity); commands that merely share a slot without clashing — e.g. AoE2's civ-exclusive
  alternatives, where each civ fields only one — get a neutral corner count of how many are stacked
  instead. Games without `GAME.setSlot` (e.g. AoE2) get a read-only card with click-to-rebind.
- **QWERTY⇄Dvorak** slide toggle — converts binds *and* relabels the keyboard. This is
  **game-agnostic**: a bind is a virtual-key code, and remapping VK codes between layouts is
  independent of the game (a load is interpreted as the current toggle position).
- **Command list** grouped into collapsible columns with a filter box. By default groups are
  ordered alphabetically and balanced across columns; a game may instead supply an order
  (`groupKey`) and strict per-category columns (`groupCategory`, see below). A game may also place
  a command in **extra groups** beyond its home group (`extraGroups(rec) → [name]`) — the *same*
  rec object, so the two views edit in sync — and override a group's column placement / card-grid
  visibility per group (`groupMeta(name, recs) → {key?, cat?, card?}`) instead of inheriting its
  first rec's. AoE2 uses both for its per-building **bundle** groups (see its README).
- **Category filter buttons** (when a game supplies `filters`) — e.g. WC3's race buttons; a
  single-select bar that narrows the list, composing with the search box. Absent for AoE2.
- **Strict category columns** (when a game supplies `groupCategory`) — instead of one balanced
  split across all groups, each category keeps its own whole columns (never mixed) and longer
  categories get proportionally more columns. WC3 (Common/Heroes/Units/Buildings/Campaign), SC2
  (General/Units/Buildings/Global), and AoE2 (Common/Units/Buildings/Global/Chronicles) all use it;
  AoE2 derives the category from each command's existing conflict-context code (no filter bar).
- **Start from bundled defaults** (when a game provides them) — a one-click button loads a
  built-in default file, so you can begin editing without picking your own file first.
- **Conflict framework:** the engine pairs up every two commands that share the exact combo
  (key + ctrl/alt/shift) and asks the active game module to classify them into three tiers —
  **confirmed** (red ⚠), **possible** (amber ⚐), **override** (blue ⓘ) — shown as key rings,
  row markers, and a toolbar badge that filters the list to flagged commands. The *rules* are
  the game's; the pairing, display, and tiers are the engine's.
- **Rebind-conflict preview:** while a command is being rebound (a capture is live), every key that
  *would* clash if it landed there — with the currently-armed modifiers — gets an inset severity ring,
  so you can pick a clean key at a glance (current-state rings give way to the preview while capturing).
  When the command sits in a keyboard **stack** (several of the selected card's commands share one base
  key via different modifiers), the preview spans the *whole* stack — each member checked at its own
  modifiers — so you can find a key clean for the whole set (the click still rebinds only the shown one).

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
  may mix and match: AoE2 supplies `groupKey`/`groupCategory` (strict columns) but no `filters` (no
  filter bar); a game that defines none of these gets the plain balanced, alphabetical, unfiltered list.
- **input** — game-specific input bits only: extra mouse buttons and any extra VK labels.
  (Dvorak / keyboard layouts are engine-level, **not** per game.)
- **icon (optional)** — `icon(rec) → url | null`: an ability/command icon for the record. When a
  game supplies it, the engine overlays each command's icon on the key it's bound to (the WC3 in-game
  command card, rendered on the keyboard) for the **selected** card, and as a temporary **hover**
  preview when the pointer is over a command row or a group heading (the collapse or 👁 button) — the
  hovered group takes precedence and reverts to the selected card on mouse-out. A game without it
  shows no icons. The URL is resolved relative to the built page, so games that use image
  assets ship them next to `site/<game>/index.html` (WC3 and AoE2 each copy an `icons/` folder) rather
  than inlining them.
- **slot (optional)** — `slot(rec) → slot index | null`: the record's slot in its building/unit's
  in-game command card, numbered row-major from the top-left (`row = slot // cols`, `col = slot % cols`).
  The card's geometry is per game via `meta.cardCols`/`meta.cardRows` (default 5×3): AoE2 is 5×3, WC3 is
  4×3. When a game supplies it, selecting/hovering a card whose commands have slots renders that card as a
  grid panel beside the keyboard (each command's icon + bound key in its real slot), tracking the same
  selected/hover card as `icon`. `null` for records with no mapped slot; a group with no slotted records
  shows no panel. Selecting or hovering a command highlights its slot (mirroring the keyboard's key
  highlight). AoE2 (`positions.json`) and WC3 (`positions.json`) both supply it.
- **learnSlot (optional)** — `learnSlot(rec) → slot index | null`: a second card shown *beside* the
  command card, for the same records at a different slot. WC3 uses it for a hero's **learn** sub-card
  (`Researchbuttonpos`), so a hero shows both its command card and its learn card side by side. When
  a group has no learn-slotted records (every non-hero), only the command card renders.
- **setSlot (optional)** — `setSlot(doc, rec, slot, card)`: move a command to a new card slot (grid
  drag-and-drop); `card` is `'command'` or `'learn'`. When present, the engine makes the card grid draggable (drop on empty = move,
  drop on filled = swap) and calls this to (a) update the game's live slot map so the panel/overlay
  repaint immediately and (b) queue the file writeback, applied at save. WC3 supplies it (writes
  `Buttonpos`); AoE2 omits it, so its card is read-only apart from click-to-rebind.
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
- **Ability-icon art occludes anything drawn *inside* a key.** When a game supplies `icon`, a
  selected/hovered card overlays each command's art as a `.keyimg` on its key — an
  `position:absolute; inset:0` child (scaled `1.12`) that fills the `overflow:hidden` key. It has
  no `z-index`, so it paints over the key's own background *and any inset `box-shadow`*. So a cue
  meant to sit **inside** a key (e.g. the rebind-preview `wclash-*` ring) is invisible on icon-bearing
  keys unless it's lifted above the art — draw it on a `::after` overlay with a `z-index` (the
  preview ring uses `z-index:2`; the icon is `z-index:auto`). Cues drawn **outside** the key border
  (the outer `.conflict`/`.clash` rings, `.capturing`'s outline/glow) are unaffected. This is why the
  drag/click clash-preview once appeared only *after* dropping onto an icon key — the pre-drop inset
  ring was hidden behind the icon, while the post-drop conflict ring is an outer one.
