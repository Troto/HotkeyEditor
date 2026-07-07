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
- **`data/wc3.json`** — the vendored dataset (unit/ability names, races, types, the shared
  common-command lists, `shown` = playable-unit allowlist, `campaign` = campaign-only units).
  Derived from an open-source editor — see **`data/SOURCE.md`** for provenance/attribution (MIT).
  As of the source-cards work, the per-unit **command lists** here are **only a cross-check** — the
  cards actually rendered come from `wc3_cards.json` (below); jcfields still supplies unit names,
  races, types, the `shown`/`campaign` lists, and the common-command sets.
- **`data/gen_wc3_data.js`** — one-off Node converter that (re)builds `wc3.json` from the upstream
  `data.js` + `index.html`. Not part of the Python build; only rerun if the upstream data changes.
- **`data/wc3_cards.json`** — `unit code → [[cmd,name] | [cmd,name,form]]`: **each unit's command
  card compiled from Blizzard's own game data**, built by **`data/gen_wc3_cards.py`** from
  `unitabilities.slk` (abilList/heroAbilList) **merged with `unitskin.txt`'s `abilSkinList`** (the
  Reforged skin lists are more current — they carry Call to Arms on the base Town Hall, Purge on the
  Shaman, Possession on the Banshee, which the older abilList omits; a unit's card is deduped by
  ability **name** so a multi-rawcode ability like Abolish Magic shows once) + the `*unitfunc.txt` production lists
  (`Trains`/`Researches`/`Upgrade`/`Revive`/`Sellunits`/`Sellitems`; `Builds` feeds the worker's
  separate Build sub-menu), placed in command-card slot order (`positions.json`). **Alternate-form
  abilities are unioned in** — when a unit has a *morph* ability (Bear Form, Destroyer Form,
  Robo-Goblin, Stone Form, …) that form's abilities are added, tagged with the alt-form unit code as
  a third entry element so the editor scopes conflicts per form. A morph is distinguished from a
  *summon* structurally: a morph references the caster itself in the ability's `DataA*`/`UnitID*`
  fields, a summon only references the spawned unit. This is **more accurate than jcfields** (it fixes
  e.g. the Obsidian Statue's morph — real code `aave` "Destroyer Form" with a card button, vs
  jcfields' buttonless `ubsp` proxy — and recovers the Barracks' `rhsb`); `gen_wc3_cards.py` prints a
  jcfields cross-check diff. Inlined into the build; the module (`setData`) uses it for `UNIT_CARD`,
  falling back to the jcfields `wc3.json commands` for anything source doesn't cover.
- **`data/wc3_names.json`** — `code → name` map that is the **source of truth for every command
  name** shown (unit-card commands, common commands, globals, and the Miscellaneous tail), built by
  **`data/gen_wc3_names.py`** from Warcraft III's own game data: the button action label from
  `strings/*.txt` (`Tip=` — "Build Barracks", "Train Footman" — preferred; `Name=` fills codes
  with no Tip; level-1 of leveled comma-lists, color/Level markup stripped), with SLK `comment`
  columns filling any gaps (see `data/SOURCE.md`). Inlined into the build; the module labels every
  record through it, falling back to the jcfields card name only for codes the game files don't name.
  The raw Blizzard SLK/txt tables + `strings/` it's built from are **not vendored** — supply them
  from a game install to regenerate (see `data/SOURCE.md`).
- **`data/wc3_items.json`** — `code → "melee" | "campaign" | "hidden"` for every item, built by
  **`data/gen_wc3_items.py`** from Blizzard's `itemdata.slk` + the `slk data/*func.txt` profiles. Item
  *purchase* hotkeys have no shop card in the base game data (only the Goblin Merchant carries a fixed
  `Sellitems=` list — everything else is placed per-map in the World Editor), **and** WC3 templates
  every item with the same fields, so most of these purchase sections are boilerplate the game never
  uses. The generator tags each item by whether its purchase hotkey is ever **reachable in a match** —
  in a shop's `Sellitems=` list, on a shop card (`Buttonpos`), or in the random drop/marketplace pool
  (`pickRandom`): `"melee"` (reachable), `"campaign"` (`class=Campaign` quest item), or `"hidden"`
  (ruled out — no shop/pool offers it). Inlined into the build; `module.js` (`bindings()`) sends
  `melee` → the **Items** column, `campaign` → the Campaign column, and **drops `hidden` from the
  list** (`hidden:true`; the section still round-trips on save). (`droppable` is a red herring — it's
  `1` for ~every item, a template default, not a usage signal.)
- **`data/wc3_misc.json`** — `code → "unbuilt"` for every unit whose build/train hotkey is dead, built
  by **`data/gen_wc3_misc.py`** from `unitdata.slk` + `abilitydata.slk` + the `slk data/*unitfunc.txt`
  profiles. Just as WC3 templates every *item* with purchase fields, it templates every *building/unit*
  with a build/train command button (a `Buttonpos` + a `[code]` Hotkey section). A large family of
  neutral buildings — the **Mercenary Camps** (one rawcode per tileset), **Dragon Roosts**, **Goblin
  Laboratory / Merchant / Shipyard**, **Tavern** — is only ever *placed in the World Editor* (they're
  in the random neutral-building pool, `nbrandom=1`), **never built by a unit**, so their "Build X"
  hotkey never fires in a match. The generator tags a unit `"unbuilt"` when it's in **no** builder /
  production / shop list (`Builds` / `Trains` / `Sellunits` / `Sellitems`) **and** referenced by **no**
  ability (a summon/hire spell would make it melee-relevant). Inlined into the build; `module.js`
  (`bindings()`) **drops `unbuilt` from the list** (`hidden:true`; the section still round-trips on
  save). (`nbrandom`/`unitClass`/`campaign` — the unit analogues of an item's `pickRandom`/`class` —
  only say the *building* is placed on maps, not that its build *command* is ever issued, so they're
  not the hide signal; producibility is.)
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
- **`data/positions.json`** — `code → command-card slot` maps (`b`/`r`/`u`) for the **command-card
  grid panel** (see below). Inlined into the build; `module.js` (`slotOf`) reads it.
- **`data/gen_wc3_positions.py`** — one-off Python script that (re)builds `positions.json` from the
  `Buttonpos` lines in `data/slk data/*func.txt`. Stdlib only; not part of the Python build.
- **`data/slk data/`** — the vendored game data tables (`*.slk`) and profile text files (`*func.txt`,
  `*skin.txt`, …) the generator scripts read; only `gen_wc3_positions.py` uses them today (for the
  `Buttonpos` values, which aren't in the SLKs). See `data/SOURCE.md`.
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
- **Refresh the card-grid positions** (rare): `python3 games/Warcraft3/data/gen_wc3_positions.py`
  (rebuilds `positions.json` from `data/slk data/*func.txt`; stdlib only).
- **Refresh the item categories** (rare): `python3 games/Warcraft3/data/gen_wc3_items.py`
  (rebuilds `wc3_items.json` from `data/slk data/itemdata.slk` + the `*func.txt` profiles; stdlib only).
- **Refresh the unbuildable-unit list** (rare): `python3 games/Warcraft3/data/gen_wc3_misc.py`
  (rebuilds `wc3_misc.json` from `data/slk data/unitdata.slk` + `abilitydata.slk` + the `*unitfunc.txt`
  profiles; stdlib only).
- **Recompile the command cards** (rare): `python3 games/Warcraft3/data/gen_wc3_cards.py`
  (rebuilds `wc3_cards.json` from `data/slk data/unitabilities.slk` + `abilitydata.slk` +
  `*unitfunc.txt` + `positions.json`; stdlib only). Prints a jcfields cross-check diff — skim it after
  a data change to catch anything source over/under-lists.
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

## Command-card grid panel
Alongside the keyboard overlay, selecting (or hovering) a card also draws that card as its real
**in-game 4×3 command grid** in the right gutter — each command's icon + bound key dropped into its
actual button slot, so the Barracks reads Footman/Rifleman/Knight across the top row, upgrades along
the bottom, Cancel bottom-right, exactly as in-game. The engine renders this generically from the
optional `GAME.slot(rec)` hook (games without it show no panel); the card geometry is `meta.cardCols`
× `meta.cardRows` (WC3 is **4×3**, AoE2 is 5×3). A **hero** additionally exposes `GAME.learnSlot`
(`Researchbuttonpos`, POS.r), so the engine draws its **learn** sub-card as a second grid beside the
command card — the ability icons at their learn-button slots (top row) next to the same abilities on
the command card. The key label is a top-left corner badge on each slot (as in-game), and
selecting/hovering a command highlights its slot.

`slotOf` maps a binding's code through **`data/positions.json`** — three `code → slot` maps
(`b` = the command's own command-card button = `Buttonpos`; `r` = the hero *learn* sub-card button =
`Researchbuttonpos`; `u` = a two-state toggle's off-state = `Unbuttonpos`), slot numbered row-major
from the top-left (`slot = row*4 + col`). It uses **`b` (the ability's own button)** for everything,
so the whole card reads together (a Paladin's Holy Light / Devotion Aura / Resurrection all on the
bottom row); an *Off* row uses `u`. It deliberately does **not** use `r`: that's the learn sub-card
(top row), so a passive aura — whose only binding is its learn key (`Researchhotkey`) — still shows
at its command-card `Buttonpos`, next to the actives, not at its learn-button slot. `null` for
commands with no fixed card slot — shop items and mercenaries are laid out from the building's sell
list at runtime, not a fixed `Buttonpos`, so they simply don't appear in the grid.

- **`data/positions.json`** — generated by **`data/gen_wc3_positions.py`** from the game's profile
  text files (`data/slk data/*func.txt`), which carry each command's `Buttonpos`/`Researchbuttonpos`/
  `Unbuttonpos=X,Y`. (The button position is *not* in the data SLKs — that field's `slk` source is
  "Profile".) Regenerate with `python3 games/Warcraft3/data/gen_wc3_positions.py`; see `data/SOURCE.md`
  for where the `slk data/` profiles come from. Coverage is ~89% of command codes (all melee
  ability/unit/upgrade/research cards; the gaps are shop/mercenary/campaign-only entries).

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
  add/remove done last so line indices stay valid);
- rewrites (or inserts) a section's `Buttonpos`/`Unbuttonpos`/`Researchbuttonpos` line for
  **command-card position edits** made by dragging a slot in the grid panel (`GAME.setSlot` →
  `setSlotDoc`). The `card` arg picks the field: a command-grid drag writes `Buttonpos` (or
  `Unbuttonpos` for an off-state), a learn-grid drag writes `Researchbuttonpos`. `parse` records
  each section's position-line index + original slot (`posLines`/`posOrig`); a drag stashes the new
  slot on the section (`_posEdit`), `save` writes it as `X,Y` (`slot = Y*4 + X`) in place or inserts
  a line where none existed, queued with the modifier structural ops. It also updates the live
  `POS.b`/`POS.u`/`POS.r` map so the panel repaints at once. Dragging a command back to its file
  original drops the edit, so a section never *net*-moved stays byte-exact.

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
across cards. `emitCommand` also **dedupes a binding per card** (keyed by group + id): units that
share a display name fold into one group — most often a building and its `_campaign` twin (e.g.
`halt` / `halt_campaign`, both "Altar of Kings") — and since the generic building commands are
literally the same line (`cmdrally` = Set Rally Point, `cmdcancelbuild` = Cancel), without this
they'd show twice on the card. The same line still appears on genuinely different cards, once each.
Cards:
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
- **Items** — item *purchase* hotkeys, lifted out of the Miscellaneous tail via `wc3_items.json`. The
  ones **reachable in a match** (`"melee"`: in a shop's `Sellitems`, on a shop card `Buttonpos`, or in
  the random drop/marketplace pool `pickRandom`) form the **Neutral Items** group in their own **Items**
  column; **Campaign Items** (`class=Campaign`: Shadow Orb Fragment, Wirt's Leg, …) go to the Campaign
  column. The rest — templated purchase sections no shop or pool ever offers — are **`"hidden"`** (see
  below). Items carry no unit/set scope, so — like Miscellaneous — they never raise conflicts (a given
  shop's live stock is per-map, so we don't treat the whole pool as one card).
- **Miscellaneous** — the catch-all for a leftover that is *none* of the above (not carded, not a
  tagged global, not an item, not a producible unit). For the melee dataset this ends up **empty**:
  every real command has a home (a unit/common card, a global group, or the Items column), and anything
  left is dead/redundant and gets hidden (see below), so no "Miscellaneous" group renders. The group
  still exists as a fallback (a record's name would resolve `NAMES[code] || wc3_names.json[code] ||
  the // comment || raw code`) for any future/custom binding the data doesn't recognize.
- **Hidden (`hidden:true`)** — dropped from the list but kept in the file (they still round-trip
  byte-exact on save), because their hotkey can't fire in a real match. Five sources:
  - **Duplicate section blocks** — the game reads only the **first** `[code]` block of a case-folded
    code collision (the codec keeps that first block as the `byCode` winner). A file with a second
    `[ACdm]` / `[adsm]` / … block has that duplicate ignored by the game, so it's dropped from the list
    while the real one stays correctly on its unit card(s). Detected structurally (a leftover bind that
    isn't its code's winner), so it needs no data table. 5 records in the bundled default.
  - **Ruled-out template items** — item purchase sections tagged `"hidden"` by `wc3_items.json`: WC3
    templates every item alike, so these are boilerplate no shop or drop/marketplace pool offers (e.g.
    the `Miscellaneous`-class duplicate rawcodes — Ring of the Archmagi ×3 — and non-pooled runes/
    glyphs). ~89 of the bundled default's Miscellaneous tail.
  - **Non-producible units** — train/build/summon sections tagged `"unbuilt"` by `wc3_misc.json`: WC3
    templates every unit with a build/train button, but a unit's hotkey only fires if a **shown**
    command-card button actually **produces** it (it's in some browsable unit's `Builds`/`Trains`/
    `Sellunits`/`Sellitems` list). Several families never are: the neutral buildings only *placed in the
    World Editor* (Mercenary Camps — one per tileset — Dragon Roosts, Goblin Laboratory/Merchant/
    Shipyard, Tavern); every unit that only appears via an **ability** — summoned/morphed/hired (Doom
    Guard, Clockwerk Goblin, the Destroyer form, Spirit Bear, …), where the *summoning ability's* hotkey
    is pressed, not the unit's train button; and units produced only by an **unshown** (e.g. campaign)
    unit — `nbal` Summon Doom Guard / `nfel` Fel Stalker are trained only by campaign Dreadlords, so
    there's no reachable produce button. Their sections are dead; the unit's own **abilities** still card
    normally. ~48 of the bundled default's tail. (Being ability-referenced does **not** rescue a unit.)
  - **Redundant orphan rawcodes** — two mechanisms: (1) a **name already carded** rule — a leftover
    whose ability is already shown on a card under a different rawcode is dropped (e.g. `auan` "Animate
    Dead" while the Death Knight binds `aua2`); and (2) a small hand-verified `HIDE` map for cases a
    name match can't catch: a redundant *build* code (`orbr` Build Reinforced Burrow — the Orc Burrow
    `otrb` is upgraded in place by Reinforced Defenses, and `orbr` isn't even a real unit), a redundant
    duplicate ability on one unit (`aenc` generic "Load" alongside the Entangled Gold Mine's real "Load
    Wisp" `slo2`), and dead abilities defined in `abilitydata` but granted to **no** unit (`aetf`
    Ethereal Form, `auuf` Incite Unholy Frenzy, the Pocket Factory internals `anfy`/`anf1`–`anf3`).
    Editing the live carded copy is what rebinds the in-game key. If the dataset changes, re-verify.
  - **Uncarded dregs** — the final fallback: a leftover that is none of carded / global / item /
    producible-unit has no home in the data, so it's dropped. In the melee default these are dead
    generic pseudo-commands (`cmdbuild`, and `cmdcanceltrain`/`cmdcancelrevive` — the real Build/Cancel
    are the carded race-specific `cmdbuild*` / `cmdcancel*` codes), a buttonless or hidden-building-only
    ability (`aatp` Prioritize — granted to the Gargoyle but with no `Buttonpos`; `aral` the Pocket
    Factory's Rally), and a nameless dummy item (`mdpb`). This is what makes the melee Miscellaneous
    empty.

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
- both on the same unit card (`same unit`) — but two commands can only really clash if they can be
  on the card at once, so within a unit we exclude **alternates**: different morph **forms** never
  coexist (a base-form ability and an alternate-form one carry different `form` tags → no clash),
  and commands sharing the **same command-card slot** are one button (a tier upgrade like
  Headhunter→Berserker, or a form toggle) → no clash; or
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
  **common → heroes → units → buildings → campaign → items** (the trailing Items column holds the
  neutral shop / powerup item-purchase hotkeys). Cards sort alphabetically by name within a
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
  Heroes / Units / Buildings / Campaign / Items); the engine (`page.html`) renders it when a game
  defines strict categories.
- **Card labels** — a unit card's heading is just the unit name for the four main races (the race
  filter already scopes the list); folded campaign races keep a `Race — ` prefix (e.g.
  `Blood Elf — …` under the Human filter) to disambiguate. Genuinely neutral units take a trailing
  `… (Neutral)` tag instead (e.g. `Voidwalker (Neutral)`), so they read as the unit name and
  interleave alphabetically by it.

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
- A single command **group can't split across columns**, so a large group (e.g. **Neutral Items**,
  or **Miscellaneous** in the Campaign category) stays a tall single column.
- No `--regen`: to change the dataset, rerun `data/gen_wc3_data.js` against the upstream files.

## Provenance / licensing
Dataset derived from **jcfieldsdev/warcraft3-hotkey-editor** (MIT) — attribution + retained
licence notice in **`data/SOURCE.md`**.
