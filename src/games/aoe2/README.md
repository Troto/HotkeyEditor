# Age of Empires II: DE — game module

The AoE2:DE module for the [Hotkey Editor](../../README.md). It reads/edits AoE2:DE hotkey
profiles (`.hkp`). It exists because the public site **hotkeyeditor.com** can't parse the
game's current ("wrapped", build 155976+) `.hkp` format.

At runtime the editor needs nothing from a game install — it reads only the small vendored
data files in `data/` (regenerated from an install on demand). See the root README for the
generic engine, the build pipeline, and how a game module plugs in.

## Files (this folder)
- **`game_module_generator.py`** — this game's build/data CLI (`--build` / `--regen`). It
  produces `data/`'s json and inlines it (via the shared root `page_assembler`) into the UI
  shell `page.html`, emitting `site/aoe2/index.html`. **`--regen` is the only step that reads
  a game install.**
- **`hkp_parser.py`** — parses/writes `.hkp` (raw-deflate zlib + `struct`). Handles both the
  old "plain" (v4.20) and new "wrapped" (v4.32+, sentinel-delimited) formats. Verified
  byte-exact round-trip, and serves as the **oracle** the browser JS port (in `page.html`) is
  checked against. Also the `.hkp` CLI: `python3 games/aoe2/hkp_parser.py <file>`. Format
  grammar is in its docstring.
- **`dvorak_convert.py`** — standalone CLI QWERTY↔Dvorak remapper for `.hkp` files (imports
  `hkp_parser`). The editor has its own in-app toggle too; this is the original tool.
- **`data/strings.json`** / **`data/card_data.json`** / **`data/civ_data.json`** — the three
  vendored data files the app runs off at runtime (no game install required). All generated
  by `--regen`:
  - `strings.json` — `{hotkey string id → display name}`, trimmed to the ~660 ids the hotkeys
    actually use (vs the game's ~21k-entry string table).
  - `card_data.json` — `{byId:{id:[group,ctx]}, chronicles, hidden}` (our curation over `hotkeys.json`).
  - `civ_data.json` — `{civCount, idToCivs:{id:[civs]}, units:[ids]}` (per-civ availability, keyed by id).
- **`../../Example Key files/`** (repo root) — sample profiles for testing.

## Commands
- **Build**: `python3 games/aoe2/game_module_generator.py --build` → `site/aoe2/index.html`
  (also refreshes the `site/index.html` launcher).
- **Regen data**: `python3 games/aoe2/game_module_generator.py --regen` — needs an AoE2:DE
  install (`AOE2_STRINGS` / `AOE2_HOTKEYS`); **not runnable without one** (e.g. in a container).
- **`.hkp` round-trip check**: `python3 games/aoe2/hkp_parser.py "<file>.hkp"`.
- **Dvorak CLI**: `python3 games/aoe2/dvorak_convert.py`.
- **Preview**: build, then `python3 -m http.server 8765` and open
  http://localhost:8765/site/aoe2/index.html (or `site/index.html` for the launcher).

## The `.hkp` format (what's in the file vs. not)
- A profile = **two files**: `<Name>.hkp` (legacy 9 "shared" menus) **and**
  `<Name>/Base.hkp` (the new remappable system: `unit_commands`/`game_commands`/
  `cycle_commands` sections + N "detached groups" = building command cards). The game
  needs both; the editor loads/saves both (the download is a zip with that structure).
- Each entry stores only: a numeric **string id** (the command), a **VK key code**, and
  ctrl/alt/shift. The file has **no names and no group/building labels** — those come
  from game data files (below). Each *occurrence* of a command id is an independent,
  separately-bindable slot (so e.g. "Tech: Wood Upgrades" appears under Lumber Camp,
  Mule Cart, and Settlement as three different ids — the remappable system exposes a
  command once per card).

## Where the game keeps its files (regen / live profiles)
- **Install** (read only by `--regen`): default `D:\SteamLibrary\steamapps\common\AoE2DE`
  (override via env `AOE2_STRINGS` / `AOE2_HOTKEYS`). Other common Steam roots are probed.
- **Live profiles** (the user's actual hotkeys): `%USERPROFILE%/Games/Age of Empires 2 DE/<steamid>/profile/`.
  **Never write into the live `profile/` folder** — read freely. The editor's download is a
  separate zip the user copies in themselves.

## Where data comes from (regen only — runtime uses the vendored JSON above)
`--regen` reads a game install and rewrites the three data files. **None of the files below
are read at runtime** — they're build-time inputs.
1. **`resources/en/strings/key-value/key-value-strings-utf8.txt`** (+ sibling
   `key-value-*strings-utf8.txt`, e.g. the paphos/Chronicles DLC) → `id → display name`.
   `load_strings()`; the result is trimmed to hotkey ids to make `strings.json`.
2. **`resources/_common/dat/hotkeys.json`** → the **authoritative grouping** (the link the
   `.hkp` lacks). `shared_hotkey_group_list` (9 menus, 1:1 with profile.hkp) + `hotkey_group_list`
   (base.hkp's sections + building cards). Each group has `data_name`, `name_string_id`
   (→ card name), and a `hotkey_list` whose commands carry `name_string_id` (= the id in the
   `.hkp`), a `data_name`, and — for the build menu — a `context` of `economic`/`military`.
   → `card_data.json` via `build_card_data()`.
3. **`resources/_common/dat/CivTechTrees/<CIV>.json`** + **`civilizations.json`** → per-civ
   availability. A civ can use a node iff its tech-tree lists it with `Node Status != NotAvailable`;
   `Use Type` gives unit / building / tech. Standard civs = `civilizations.json` entries with
   `era == "base"` minus Gaia (the 6 `antiquity` entries are the Chronicles civs, excluded). Each
   node is matched to its hotkey command id by **normalised name** (`build_civ_data` / `_norm_name`),
   so the runtime civ check is pure id lookup → `civ_data.json`.

## Groups vs. Contexts — the core model
`build_card_data()` emits **`byId = {commandId: [displayGroup, contextCode]}`** plus a
`chronicles` id list. Two distinct concepts:
- **display group** = the heading shown in the list (Stable, Go-To Commands, Production
  Buildings, …). `groupNameOf(r)` in the page.
- **context code** = the *conflict scope* — when a command is actually active in-game.
  `recContext(r)`.

**Context codes:**
- `G` — always-active global (Select-all, Go-To, Control Groups, Camera/Scroll, Zoom, Game/Chat).
- `R` — replay/spectator mode.
- `CAMP` — campaign/Chronicles content (hidden by default).
- `U:<type>` — a unit is selected. types: `any`, `nonsiege`, `villager`, `military`,
  `siege`, `monk`, `trade`, `fishing`, `hybrid`. `any` overlaps every type; `nonsiege`
  overlaps all but `siege` (e.g. Garrison); two distinct singleton types never coexist.
- `B:<tab>` — villager build menu tab, `eco`/`mil` (mutually exclusive tabs).
- `D:<card>` — a building is selected: a specific card (`D:Stable`) or `D:any` for a
  command on every building (gather points).
- `T:gt` — garrisons/transports layer (Unload/Ungarrison): isolated, clashes only within itself.
- `X:...` — fully isolated (e.g. `X:autoscout`): never clashes (used for special toggles).

## Curation (our own data, layered on `hotkeys.json` in `build_card_data`)
The authoritative groups are good but coarse, so we reorganise (all editable in one place):
- `CYCLE_COMMAND` merged into one **Go-To Commands**.
- `GROUP_COMMAND` split **Control Groups 1-10 / 11-20** by the `#N` in the name (`_ctrl_split`).
- `VILLAGER_HOTKEYS` split by the json `context` field → **Build Economic Buildings** /
  **Build Military Buildings** (contexts `B:eco`/`B:mil`); `VILLAGER_BUILD_FISH_TRAP` →
  **Fishing Ship Build** (`U:fishing`). (`NEXT_PAGE` / "More Items" is *not* the build toggle —
  it's the Dock's second command page; see `_ABILITY` → Dock.)
- The big base `UNIT_COMMAND` group is split by per-command `data_name` via the **`_ABILITY`**
  map into: **Unit Commands** (Stop/Garrison/Delete only; Garrison is `U:nonsiege`),
  **Villager Commands**, **Siege Commands** (pack/unpack/unload-siege/attack-ground),
  **Hybrid Units** (Change Mode), **Monk Commands**, **Production Buildings** (gather points),
  **Garrisons/Transports** (Unload/Ungarrison, `T:gt`), **Trade Commands**; Go-Back-to-Work → Dock.
- `MILITARY_UNITS` stances → **Military Unit Commands**; its `BUILD_MENU` (the generic
  "Build") → Villager Commands **but added to the always-`hidden` set** (the eco/mil build
  menus make it redundant); `AUTO_SCOUT` → isolated `X:autoscout` (coexists with Stop).
- Building cards → group = card name, context `D:<name>`.
- `CAMPAIGN_*` groups → `chronicles` (hidden).
- The `hidden` list in `card_data` = ids dropped from the view unconditionally (unlike
  `chronicles`, which a toggle reveals). Saved files keep them byte-for-byte.
- **Battle for Greece (Chronicles) content** → also added to `chronicles` (hidden by
  default, shown with the toggle): any command in the `419000+` string-id band (War
  Chariot, Hoplite, Polemarch, the ships, hero select/go-to, doctrine/satrapy techs, …)
  plus the four BfG-only cards (`FORT`/`PORT`/`SHIPYARD`/`OUTPOST_HOTKEYS`). Each keeps
  its real group/context so conflicts still work if shown. See `_is_bfg`. The generic
  `400000-400021` commands (Seek Shelter / All Back to Work / Drop Off Resources) are
  *not* BfG and stay visible.

**To re-categorise a command, edit the `_ABILITY` map / the per-group branches in
`build_card_data()`** — it's the single source. The data is keyed by id (universal across
profiles of a game version); after editing curation **or** after a game patch, rebuild all
three vendored files with **`--regen`** (needs a game install).

## Conflict detection (frontend `ctxClassify` + `computeConflicts`)
The generic engine pairs up every two commands that share the exact combo (code+ctrl+alt+shift)
and asks this module whether they can co-occur. AoE2's rules:
- **Mutex slots** (`MUTEX_GROUPS`, by command id) → never clash. For civ-exclusive sets the
  civ dataset can't resolve from names: the generic **Unique Warships** slot vs **Thirisadai**;
  the global **Go to / Select all** commands for the civ-unique buildings (Donjon / Krepost /
  Mule Cart), which are otherwise `G`+`G` = confirmed; and **Xolotl Warrior** vs the **Scout
  Cavalry / Hussar** line (the Xolotl is trained only by the American civs — which have no Scout
  line — from captured/scenario Stables, so the two never share a Stable card). Checked first in
  `ctxClassify`.
- **Isolated ids** (`ISOLATED_IDS`, by command id) → never clash with anything, because they
  live in their own sub-mode that isn't active alongside ordinary bindings (e.g. **Remove Gather
  Point**, only reachable after Set Gather Point is pressed). Checked first in `ctxClassify`.
- **Note pairs** (`NOTE_PAIRS`, by command id) → shown as an informational note (override tier:
  blue ⓘ, no key ring, not a conflict) with a custom message instead of a civ flag — for pairs
  that are co-bindable but practically a non-issue (e.g. **Infantry Unique Units** vs **Eagle
  Warrior / Fire Lancer**: only matters with an Italian ally's Condottiero or a conversion).
- `G`+`G` / `R`+`R` → **confirmed**.
- `G` + any contextual → **override** (caution: the active card/selection shadows the global).
- same `U` layer → confirmed iff unit-types overlap (`uTypesOverlap`).
- `B` layer (villager build menu): different tab (eco vs mil) → no clash; **same tab** → civ
  check by command id (`civsForId`, `civ_data.json`): civ-exclusive buildings (Feitoria, Settlement,
  Donjon, Krepost, Mule Cart, … and Settlement vs the Mill/Lumber/Mining it replaces) → suppressed;
  overlapping or can't-verify → confirmed.
- same `T` layer → confirmed iff identical sub-key.
- `D` layer: `D:any` overlaps all cards → confirmed; different cards → no clash; **same card**
  → **universal slots** first (`UNIVERSAL_SLOTS`, by id — the generic Unique-Unit / Elite-UU /
  Unique-Castle / Unique-Imperial slots every civ has at its Castle; civ-generic names so the
  dataset can't resolve them, but all civs always have all of them) → **confirmed**; otherwise a
  civ check by id (`civsForId` / `isUnitId`): both units + civ overlap → confirmed; building/tech
  overlap → **possible**; civ-exclusive (no shared civ) → suppressed; can't civ-verify → **possible**.
- different layers → no clash. Three tiers shown: **confirmed** (red ⚠), **possible** (amber ⚐),
  **override** (blue ⓘ). Civ availability is keyed by command id (`civ_data.json`), precomputed at
  `--regen` time by matching tech-tree node names to hotkey command names (`_norm_name`).

This makes it context-aware (villager vs military, eco-build vs mil-build, different building
cards never false-flag) — unlike the in-game checker which flags any duplicate key globally.

To extend conflict handling **without** an install, edit `MUTEX_GROUPS` / `NOTE_PAIRS` /
`ISOLATED_IDS` in the embedded JS (pure frontend, by command id).

## AoE2-specific UI notes
- **Mouse inputs** use VK codes **251–255** (ext buttons / middle / wheel up-down); the on-screen
  mouse exposes them as bindable keys.
- **Chronicles** (Battle for Greece) content is hidden by default; a toggle reveals it. Hidden and
  Chronicles entries are kept in state so **saving preserves them byte-for-byte** — hiding is
  view-only.

## Gotchas
- Save preserves hidden (Chronicles) entries byte-for-byte — hiding is view-only.
- Don't write into the live game `profile/` folder at all; read freely.
- "Infantry Unique Units" (Barracks, **id 19125**) = the slot for a civ's **infantry** unique unit
  (Huskarl / Condottiero / Flemish Militia / Serjeant) — distinct from the Castle "Unique Unit".
- The three generic `400000–400021` commands (Seek Shelter / All Back to Work / Drop Off
  Resources) were judged base-game and **left visible** (not BfG). Revisit if any turns out
  Chronicles-only.

## Notes / open items
- `civ_data.json` could be made smaller (it currently repeats the full civ-name list per id).

## Provenance / licensing
The `hkp_parser` logic derives from [`crimsoncantab/aok-hotkeys`](https://github.com/crimsoncantab/aok-hotkeys),
whose LICENSE is **public domain** → no obligation; a courtesy credit comment is kept in
`hkp_parser.py`. No `LICENSE`/`NOTICE` file is required.
