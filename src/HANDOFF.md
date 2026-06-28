# Session Handoff — project state & context

Written to let a fresh Claude Code session (incl. one running in a container) resume work.
**Start by reading [README.md](README.md)** — it has the architecture, file map, the `.hkp`
format, the group/context model, the full conflict-detection rules, and gotchas. This file
adds the things README doesn't: recent-session context, environment facts, and open threads.

## Running in a container — important caveats
- **No AoE2:DE game install is present**, so `python hotkey_editor.py --regen` **cannot run**
  and you **cannot validate against live game data**. Don't try to fetch game files.
- That's fine: the three vendored data files (`strings.json`, `card_data.json`, `civ_data.json`)
  are committed in the repo, so the app **runs fully offline** and all grouping/conflict logic
  works. The app reads *only* those files at runtime.
- The original dev machine had the install at `D:\SteamLibrary\steamapps\common\AoE2DE`
  (override via env `AOE2_STRINGS` / `AOE2_HOTKEYS`); live profiles at
  `%USERPROFILE%/Games/Age of Empires 2 DE/<steamid>/profile/`. Sample profiles are in
  `Example Key files/`. Only `--regen` needs the install.

## Constraints (hard requirements)
- **Python 3.7**, **stdlib only** (no walrus `:=`, no `bytes.hex(sep)`).
- **Byte-exact `.hkp` round-trip** — binary work lives in `hkp_parser.py` (the oracle/CLI) and an
  equivalent JS port embedded in `page.html` (what the browser actually runs); both are verified
  byte-exact. The editor only edits the parsed structure and rebuilds.
- A profile = **two files**: `<Name>.hkp` (legacy shared menus) **and** `<Name>/Base.hkp`
  (remappable system). Both must be written; the download is a zip with that structure.
- **Never write into the live game `profile/` folder.** Read freely.
- Build: `python3 hotkey_editor.py --build` → `index.html` (the deployable single file). Preview
  with `python3 -m http.server 8765`, then open `index.html`.

## Architecture (current)
- App = a single self-contained `index.html` (no server), built from `page.html` + the data by
  `python3 hotkey_editor.py --build`. **`page.html` is the source**; `index.html` is generated and
  hosts anywhere static (or opens offline). Conflict detection, all UI, **and `.hkp` parsing/
  writing** run in that page's JS — the parser is a JS port of `hkp_parser.py` (raw deflate via
  the browser's native `deflate-raw` streams).
- **Runtime reads only three vendored JSON files** (no install):
  - `strings.json` — `{hotkey string id → name}` (~660 ids).
  - `card_data.json` — `{byId:{id:[group,ctx]}, chronicles:[ids], hidden:[ids]}` (curation over the
    game's `hotkeys.json`).
  - `civ_data.json` — `{civCount, idToCivs:{id:[civs]}, units:[ids]}`, **keyed by command id**.
- `python hotkey_editor.py --regen` rebuilds all three from a game install (`build_card_data`,
  `build_civ_data`, `load_strings`, `_find_dat_dir`, `regen()`). This is the **only** install read.
- Conflict context comes from `card_data` (`G`/`R`/`U:`/`B:`/`D:`/`CAMP` codes); civ availability
  from `civ_data` by id. See README "Conflict detection".

## What changed in the session that produced this handoff (newest first)
1. **Made the app fully self-contained / install-derived** and removed all external-origin files:
   - Deleted `aoe2_civdata.json` (was from the community *aoe2techtree* dataset). Civ data now
     comes from the install's `resources/_common/dat/CivTechTrees/<CIV>.json` + `civilizations.json`
     (a civ has a node iff `Node Status != NotAvailable`; `Use Type` = Unit/Building/Tech; standard
     civs = `civilizations.json` `era=="base"` minus Gaia = 53).
   - Deleted `hotkey_strings.py` (was from the hotkeyeditor.com repo) and the dead `/groups.json`
     endpoint + frontend `GROUPS`.
   - **Civ conflict matching is now by command id** (`civsForId`/`isUnitId`); the name bridge
     (`_norm_name`) runs once at `--regen`, not at runtime.
2. **Conflict mechanisms** (frontend, in `ctxClassify`):
   - `MUTEX_GROUPS` — civ-exclusive slots that can never co-occur, so never clash. Currently:
     Thirisadai↔Unique Warships; the global Go-to / Select-all for Donjon/Krepost/Mule Cart.
   - `NOTE_PAIRS` — override-tier informational note (blue ⓘ, not a conflict) with a custom
     message. Currently: Infantry Unique Units ↔ Eagle Warrior/Fire Lancer.
   - `B` layer (villager build menu) now does the same civ-overlap check as the `D` layer, so
     civ-exclusive buildings (Feitoria/Settlement/Donjon/Krepost/Mule Cart, and Settlement vs the
     Mill/Lumber/Mining it replaces) no longer false-flag.
3. **Battle for Greece / Chronicles hiding**: `card_data.chronicles` now also includes the
   `419000+` string-id band + the BfG-only cards (`FORT`/`PORT`/`SHIPYARD`/`OUTPOST_HOTKEYS`),
   via `_is_bfg`, on top of the existing `CAMPAIGN_*` groups. Hidden entries keep their real
   group/context and stay in state for saving.
4. **A batch of fixes**: heading selection toggle + highlight persists through a rebind; keyboard
   centered; "More Items" (`NEXT_PAGE`) regrouped to the Dock; build headings renamed to
   **Build Economic Buildings / Build Military Buildings**; the redundant generic **"Build"**
   command (id 19352) added to the always-`hidden` list.
5. **Docs**: heavy docs moved out of `CLAUDE.md` into `README.md`; `CLAUDE.md` is now a short
   pointer (it should stay minimal — it's auto-loaded every query).
6. **Licensing pass**: the `hkp_parser` logic derives from `crimsoncantab/aok-hotkeys`, whose
   LICENSE is **public domain** → no obligation; the courtesy credit comment in `hkp_parser.py`
   was kept. The hotkeyeditor.com mouse-code attribution comment was removed (it only cited a
   game fact). No `LICENSE`/`NOTICE` file is required.

## Useful facts / gotchas
- `card_data.hidden` = always hidden (the redundant "Build"); `card_data.chronicles` = hidden by
  default but revealable via the Chronicles toggle. Both stay in state so saving preserves them.
- "Infantry Unique Units" (Barracks, id 19125) = the slot for a civ's **infantry** unique unit
  (Huskarl / Condottiero / Flemish Militia / Serjeant) — distinct from the Castle "Unique Unit".
- Three generic `400000–400021` commands (Seek Shelter / All Back to Work / Drop Off Resources)
  were judged base-game and **left visible** (not BfG). Revisit if any turns out Chronicles-only.
- To re-categorise a command: edit the `_ABILITY` map / the per-group branches in
  `build_card_data()`, then `--regen` (needs an install — so not doable in a container).
- To extend conflict handling without an install: edit `MUTEX_GROUPS` / `NOTE_PAIRS` in the
  embedded JS (pure frontend, by command id).

## Open / possible future work
- **Static hosting** (Cloudflare Pages was discussed): the app could become a pure client-side
  static site — port `hkp_parser` to JS, **or** run the existing Python via Pyodide in-browser
  (keeps byte-exactness) — serving the three JSON files as static assets. Not started.
- `civ_data.json` could be made smaller (it repeats full civ-name lists per id).

## Working style the user prefers
- Prefers markdown over Word docs. Say so when unsure of a fact rather than guessing. Likes to
  discuss/confirm approach before large changes.
