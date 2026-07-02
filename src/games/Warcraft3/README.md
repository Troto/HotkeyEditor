# Warcraft III — game module

The Warcraft III module for the [Hotkey Editor](../../README.md). It reads/edits the classic
**`CustomKeys.txt`** hotkey file (the text format used by both classic WC3 and Reforged's
"custom hotkeys"). See the root README for the generic engine, the build pipeline, and how a
game module plugs in.

At runtime the editor needs nothing from a game install — the module inlines a small vendored
dataset (`data/wc3.json`) plus a bundled default file. The folder is `games/Warcraft3/`
(capitalised) but the site **slug is lowercase `warcraft3`** (→ `site/warcraft3/`); the slug
comes from `_GAME_SLUG`, not the folder name.

## Files (this folder)
- **`game_module_generator.py`** — this game's build CLI (`--build` only; **no `--regen`** — the
  dataset is static, not read from a game install). Inlines `module.js` + `data/wc3.json` **and**
  the bundled defaults file into the UI shell `page.html` (via the root `page_assembler`),
  emitting `site/warcraft3/index.html`.
- **`module.js`** — everything game-specific: the `CustomKeys.txt` codec, the naming/grouping
  model, conflict rules, the race filter + category ordering, and the `GAME.*` wiring. Injected
  into the shell at the `/* __GAME_MODULE__ */` marker; wrapped in an IIFE so its internals stay
  private (it only registers `GAMES.warcraft3`).
- **`data/wc3.json`** — the vendored dataset (unit/ability names, races, types, per-unit command
  cards, the shared common-command lists, `shown` = playable-unit allowlist, `campaign` =
  campaign-only units). Derived from an open-source editor — see **`data/SOURCE.md`** for
  provenance/attribution (MIT).
- **`data/gen_wc3_data.js`** — one-off Node converter that (re)builds `wc3.json` from the upstream
  `data.js` + `index.html`. Not part of the Python build; only rerun if the upstream data changes.
- **`data/wc3_names.json`** — `code → name` map that is the **source of truth for every command
  name** shown (unit-card commands, common commands, globals, and the Miscellaneous tail), built by
  **`data/gen_wc3_names.py`** from Warcraft III's own game data: the button action label from
  `strings/*.txt` (`Tip=` — "Build Barracks", "Train Footman" — preferred; `Name=` fills codes
  with no Tip; level-1 of leveled comma-lists, color/Level markup stripped), with SLK `comment`
  columns filling any gaps (see `data/SOURCE.md`). Inlined into the build; the module labels every
  record through it, falling back to the jcfields card name only for codes the game files don't name.
  The raw Blizzard SLK/txt tables + `strings/` it's built from are **not vendored** — supply them
  from a game install to regenerate (see `data/SOURCE.md`).
- **`data/wc3_icons.json`** — `{ classic: code → icon basename }` for the on-keyboard **ability-card
  icon overlay** (see below), extracted from `data.icons.classic` in the upstream `data.js`. Inlined
  into the build; `module.js` (`iconOf`) turns a binding's code into `icons/classic/<basename>.png`.
- **`data/icons/classic/*.png`** — the 734 vendored classic ability icons those basenames reference
  (from jcfields' `www/icons/classic/`, MIT — see `data/SOURCE.md`). The build **copies this tree next
  to the page** as `site/warcraft3/icons/` (~8 MB — too large to inline), so it works on any static
  host or opened straight off disk. Only the classic set is vendored (it covers every carded command;
  the upstream reforged set is partial — no classic/reforged toggle yet).
- **`data/gen_wc3_icons.js`** — one-off Node script that (re)builds `wc3_icons.json` and, with
  `--download`, fetches the classic PNGs into `data/icons/classic/`. Not part of the Python build.
- **`HotkeyFiles/`** — sample/oracle `.txt` files (not read at runtime except the bundled default,
  which is inlined at build time):
  - **`Sensible Reforged CustomKeys.txt`** — the canonical test fixture **and** the bundled
    "Load defaults" file: the Reforged defaults merged with a community "sensible defaults" set
    (see below). CRLF.
  - **`Default Reforged CustomKeys.txt`** — the unmodified Reforged defaults (CRLF).
  - **`Old CustomKeys.txt`** — the original pre-Reforged sample (LF).
  - **`SensibleDefaults.txt`** — the community sensible-defaults source used to build the merge.

## Commands
- **Build**: `python3 games/Warcraft3/game_module_generator.py --build` → `site/warcraft3/index.html`
  (or `python3 build.py` for all games). Refreshes the `site/index.html` launcher.
- **Refresh the dataset** (rare): `node games/Warcraft3/data/gen_wc3_data.js <data.js> <index.html>`
  with the two upstream files (see `data/SOURCE.md`).
- **Refresh the icons** (rare): `node games/Warcraft3/data/gen_wc3_icons.js <data.js> --download`
  (rebuilds `wc3_icons.json` + re-vendors `data/icons/classic/`; see `data/SOURCE.md`).
- **Preview**: build, then `python3 -m http.server 8765` and open
  http://localhost:8765/site/warcraft3/index.html.

## Ability-card icons on the keyboard
When you select a single command card (click a group heading), each of that card's commands shows
its **in-game ability icon on the key it's bound to** — so a unit's command card reads on the
keyboard the way it does in-game (e.g. the Death Knight's Death Coil/Death Pact/Unholy Aura/Animate
Dead land on C/E/U/D). **Hovering** a command row, or a group heading's collapse or 👁 button, previews
that group's icons the same way; the hover takes precedence over the selected card and reverts on
mouse-out. The engine drives this generically through the optional `GAME.icon(rec)` hook (games
without it — AoE2 — show no icons); this module implements it via `iconOf`, mapping a binding's code
through `wc3_icons.json` to a relative `icons/classic/<basename>.png`. Icons clear when the card is
deselected. See `data/SOURCE.md` for the icon provenance.

## The `CustomKeys.txt` format
- Plain-text INI: **`[ABCD]`** sections keyed by a 4-char ability/command code, `Key=Value`
  lines, a blank line between sections. Comment lines (`//…`) and any keys other than the three
  below are **metadata to preserve verbatim** (`Buttonpos`, `Tip`, `Modifier`, `MerchantAvailable`,
  `GameCommand`, … — even a real `Hoktey=` typo in some files).
- **Editable bindings:** `Hotkey`, `Unhotkey`, `Researchhotkey`.
- **Values** vary: a single letter (`A`–`Z`); a **comma-list per ability level** (`A,A,A`, and
  they can differ, e.g. `C,G`); or a **numeric VK code** for everything else. **Digit keys are VK
  codes too** (the `8` key is `56`, `1` is `49`), so a *bare single digit* is a VK code, not the
  character — `8`=Backspace, `9`=Tab, `1`/`2`=mouse buttons, `27`=Esc. A lone space (`Hotkey= `)
  = unbound.
- **`Modifier=`** `Alt`/`Ctrl`/`Shift`/`Ctrl_or_Alt` — **per section** (shared by that section's
  bindings). **`UnhotkeyId=`** marks a genuine two-state button (Call to Arms / Back to Work).
- Codes are matched **case-insensitively** (the game lower-cases them and uses the first block on
  a collision). Files are **CRLF (Reforged) or LF (classic)** — both round-trip.

## The codec (line-preserving)
`parse(text) → {lines, sections}`, `unparse`, `setValue`. The doc keeps the file's original
`lines[]` and only rewrites a binding line's **value** when it actually changes, so an unedited
file round-trips **byte-for-byte** (blank lines, trailing spaces, key order, comments, CRLF/LF,
trailing newline). `save()`:
- rewrites changed `Hotkey`/`Unhotkey`/`Researchhotkey` values (VK → token; a comma-list rebind
  sets **all levels** to the new key);
- **mirrors `Researchhotkey` → `Hotkey`** when a section has both and the Hotkey changed (they're
  identical in practice — see below);
- rewrites / inserts / removes the per-section `Modifier=` line to match ctrl/alt/shift (structural
  add/remove done last so line indices stay valid).

VK model: letter↔VK (`Q`↔81), numeric VK passthrough (Esc=27…), comma-list read as level-1 and
the level count remembered; a rebind writes every level.

## Names / grouping model (unit-centric cards)
The opaque doc is `{ ck, binds, byCode, name }`. `binds` = the unique editable lines (one per
section × channel) — these are the engine's entries (`forEachEntry`/`save` iterate them).
`byCode` indexes them by lower-cased code.

`bindings(doc)` produces **one record per (command card, command)** — a WC3 ability appears on
many cards, so the same binding is emitted once per card, all records **sharing the binding's
`id`/`e`**. The engine already (a) groups records by `id` so one edit propagates to every card,
and (b) skips same-`id` pairs in conflict detection so an ability never clashes with itself
across cards. Cards:
- **Shared common cards** — `Common — Unit / Hero / Non-attacking / Tower Commands` (Move, Stop,
  Attack, …). Shown once each rather than repeated under every unit; they still conflict against a
  unit's abilities (see below).
- **Per-unit cards** — the unit's own abilities, grouped as `Race — Unit`. Only **playable/shown**
  units (the `shown` allowlist) get cards, plus the build sub-menus they open.
- **Global commands** — bindings not on a unit card but tagged by a `*Command` metadata key
  (control groups, camera, menu, item/hero slots, subgroup) are grouped into named cards
  (**Control Groups**, **Camera**, **Menu Commands**, **Selection & Items**) and placed in the
  first (common) category — they're global melee hotkeys, so they show under every race. Observer/
  Replay commands are grouped too and share that same common column (trailing the melee globals),
  but they form a separate `spectator` **conflict** scope so they never clash with in-game play —
  column placement and conflict scope are independent. Friendly names come
  from a `GLOBAL_NAMES` map keyed by section code — originally transcribed from Reforged's default
  hotkey-options screens and corroborated by the `//` comment the source file places directly
  **above** each section (the screenshots were a one-off reference and are no longer in the repo).
- **Miscellaneous** — bindings that are neither on a card nor a tagged global (abilities for
  campaign/neutral/custom units the dataset has no card for — often extra instances of an ability
  that IS carded elsewhere, e.g. a second Anti-magic Shell rawcode, or item pickups like runes,
  Shadow Orbs, scrolls). This group sits in the **same column category as Campaign**. Nothing is
  hidden. A record's name is `NAMES[code] || wc3_names.json[code] || the section's // comment ||
  raw code`: `wc3_names.json` (~2268 codes, real display names from the game's strings files) names
  everything; `NAMES` is an (empty) manual-override map for any edge case the game data gets wrong.
  In the bundled default, nothing stays raw.

Every carded/common command name is resolved the same way — through `wc3_names.json` (the game's
own strings, preferring the `Tip=` action label), with the jcfields `wc3.json` card label used only
as a fallback for the handful of codes the game files don't name. So the build command reads "Build
Barracks", the barracks' train command reads "Train Footman", and a hero ability reads "Holy Light"
— the actions the game shows.

Simplifications (with source data behind them):
- **Hero research row dropped.** Every section with both `Hotkey` and `Researchhotkey` has them
  **identical**, so we show one row (the ability hotkey) and mirror the research line on save;
  research-**only** passives (auras) show their learn key as the ability's row.
- **`Unhotkey` "— Off" row** only for genuine two-state buttons (those with `UnhotkeyId=`, e.g.
  Call to Arms / Back to Work). Most abilities carry a leftover `Unhotkey` (e.g. Gather) that
  isn't a real hotkey — it's kept in the file but not shown and never raises a conflict.

## Conflict model
Records carry a **channel**: `active` (a binding with a `Hotkey`) or `research` (a
`Researchhotkey`-only learn/upgrade key). These live on different sub-cards, so they never
conflict across channels. `classify(a, b)` (the engine has already bucketed by exact combo and
skipped same-binding pairs) → **confirmed** when same channel **and** the two share a card:
- both on the same unit card (`same unit`), or
- both in the same shared scope (`same set`) — a common card, or the melee-`global` scope (all
  control-group/camera/menu/selection globals share one scope), or the `spectator` scope, or
- one is a common-card command and the other a unit ability whose unit **type** puts that common
  set on its card (so the shared common cards still conflict against per-unit cards).

`context(r)` = `u:<unit>` / `c:<set>`; `ctxLabel` maps those to the card label. No `possible` /
`override` tiers are used (yet) — WC3 conflicts are straightforwardly confirmed.

## Race filter + category columns (engine seams, WC3-specific data)
Both are generic engine features (see root README) that this module drives:
- **Race filter** — `filters` = Human / Orc / Undead / Night Elf / Neutral (`meta.filterLabel`
  `Race:`). `recFilters(rec)` → the races a record belongs to: **generic common commands → every
  race** (always shown); a unit → its **folded** race (campaign races map to their base via
  `campaignRaces` — Blood Elf→Human, Draenei→Orc, Demon→Undead, Naga→Night Elf); anything else
  → Neutral.
- **Column ordering** — `groupKey(rec)` orders groups by **category → name** (alphabetical within
  each column); `groupCategory(rec)` turns on strict per-category columns. Category order:
  **common → heroes → units → buildings → campaign**. Cards sort alphabetically by name within a
  category — races **interleave** rather than clustering (a specific race filter shows one race
  anyway, so this only affects the "All" view); the sole non-alphabetical bit is the **Common**
  column's curated tier order (shared common cards → melee globals → observer/replay spectator). A **campaign-only** unit (from the `campaign`
  list) goes to the campaign column regardless of its type, so the melee categories are exactly
  what's used in a melee match. A **main-race** build sub-menu (type `other`, e.g. `cmdbuildhuman`)
  is detected in `catOf` and grouped with **Buildings**; the campaign races' build menus
  (`cmdbuildnaga`/`bloodelf`/`draenei`) go to **Campaign** instead. Any other melee `other`-typed
  unit (e.g. the Gargoyle) falls to **Units**. The common column also holds the melee globals and
  the observer/replay (spectator) commands.
- **Column titles** — `categoryTitle(id)` supplies the header printed atop each column (Common /
  Heroes / Units / Buildings / Campaign); the engine (`page.html`) renders it when a game defines
  strict categories.
- **Card labels** — a unit card's heading is just the unit name for the four main races (the race
  filter already scopes the list); folded campaign races keep a `Race — ` prefix (e.g.
  `Blood Elf — …` under the Human filter) to disambiguate. Neutral cards keep their prefix too.

## Where the data comes from
`data/wc3.json` is derived from the open-source **jcfieldsdev/warcraft3-hotkey-editor** (MIT) —
see **`data/SOURCE.md`** for the full attribution and the retained licence notice. Two upstream
files feed the converter:
- **`data.js`** → `units` (name/race/type/command cards), `common`, `buildCommands`,
  `campaignRaces`. The huge icon map is dropped; the numeric `type` enum is mapped to strings.
- **`index.html`** → `shown` (the browsable `#code` anchor links = playable units; `data.units`
  also holds campaign/boss units used only for hotkey resolution) and `campaign` (units listed
  under a per-race **`<h3>Campaign</h3>`** section rather than `<h3>Melee</h3>` — the reliable
  melee-vs-campaign split).

The **bundled defaults** (`Sensible Reforged CustomKeys.txt`) are inlined into the build (read
with `newline=''` so the CRLF survives) and exposed via `codec.loadDefault`. It's the Reforged
defaults with each binding checked against the community `SensibleDefaults.txt` and overridden
where the Reforged default was odd (≈15 keys — mostly an overloaded `S`/`K`), producing a
conflict-free starting set.

## Gotchas
- The `CustomKeys.txt` mentions in `module.js` / the generator are the **game's real filename**
  (what users load and what the download is named) — not the repo test fixture. The fixture is
  `HotkeyFiles/Sensible Reforged CustomKeys.txt`.
- Case-folded section collisions: `byCode` keeps the first block (matching the game); the rest of
  the binds still round-trip on save.
- A single command **group can't split across columns**, so the one large **Miscellaneous** group
  stays a tall single column (in the Campaign column category).
- No `--regen`: to change the dataset, rerun `data/gen_wc3_data.js` against the upstream files.

## Provenance / licensing
Dataset derived from **jcfieldsdev/warcraft3-hotkey-editor** (MIT) — attribution + retained
licence notice in **`data/SOURCE.md`**.
