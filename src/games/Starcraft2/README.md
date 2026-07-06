# StarCraft II — game module

The StarCraft II module for the [Hotkey Editor](../../README.md). It reads/edits a
**`.SC2Hotkeys`** profile (the INI hotkey files under `Documents\StarCraft II\Hotkeys\`), scoped
to **Legacy of the Void multiplayer**. See the root README for the generic engine, the build
pipeline, and how a game module plugs in.

At runtime the editor needs nothing from a game install — the module inlines a vendored dataset
(`data/sc2.json` + `data/sc2_icons.json`) carrying the full default bindings, command-card grid
positions, names, and icons. The folder is `games/Starcraft2/` (capitalised) but the site **slug
is lowercase `starcraft2`** (→ `site/starcraft2/`); the slug comes from `_GAME_SLUG`.

## The `.SC2Hotkeys` format (and why this module differs)

A `.SC2Hotkeys` file is an INI with `[Settings]`, `[Hotkeys]`, and `[Commands]` sections. Under
`[Commands]`, each line is `Command=Key` (a **Universal** command, one hotkey shared by every
unit — Move, Attack, Stim…) or `Command/Unit=Key` (a per-unit hotkey). The key value is a token
like `Q`, `Shift+Q`, `Control+Alt+D`, `Escape`; blank means unbound.

**The file is sparse** — it lists only the commands whose key *differs* from the game default;
everything absent uses the built-in default. So unlike AoE2/WC3 (whose files contain every
binding), this module:
- carries the full default set in `data/sc2.json` and treats a loaded file as a **patch** over it
  (so **Load defaults** works with no file at all), and
- on **save** writes back only the differences, preserving the `[Settings]`/`[Hotkeys]` bodies and
  any `[Commands]` line for a command the dataset doesn't model.

## Grouping & conflict model

- A **binding** is one editable hotkey, keyed so that (a) a Universal command is one binding shared
  wherever it appears (edit once, applies everywhere), and (b) within a display group a command
  carried by several unit-forms (Overlord vs OverlordTransport) is ONE row that still remembers
  every `.SC2Hotkeys` name it covers — so saving writes them all (`bind.saveNames`).
- **Grouping**: most commands group by their card (`<unit>` + sub-card label). Shared groups are
  pulled out so they show once instead of on every card: **Unit Commands** (movement + `Cancel` —
  Move/Stop/Hold/Attack/Patrol/Cancel) and **Under Construction** (Halt/Select Builder, only shown
  while a building is being built). Building morph-states (Orbital Command, Lair/Hive, flying forms)
  stay as separate groups. The **attack variants** (`AttackWorker`, `AttackRedirect`, …) fold into a
  single `Attack` (the game file only ever has `Attack`).
- **Global hotkeys** (the `[Hotkeys]` INI section — control groups, camera, chat, minimap, menu,
  co-op commander abilities) are parsed into editable bindings grouped by family (`GLOBALS` in
  `module.js`); they carry the Standard-profile default where well-known (control groups, subgroup,
  chat, menu) and share one `'global'` conflict scope (they don't clash with command-card keys).
- Columns are by **type** (like Warcraft III): **General** (Unit Commands + Under Construction),
  **Global**, **Units**, **Buildings** — race is the filter, not a column. A unit's type is
  jcfieldsdev's `type` (by name / caster id / base id), falling back to mobility (a unit with a
  `Move` command is a Unit, otherwise a Building); it's the `kind` field in `sc2.json`. Groups sort
  alphabetically within a column, and commands sort alphabetically within a group.
- **Conflicts** (`classify`): two commands clash iff they're on the same card and different slots
  (`context` = `u:<unit>:<cardId>`; same-slot buttons are mutually-exclusive states). The Unit
  Commands set sits on every mobile unit's card, so a movement command also clashes with a
  unit-specific command whose card actually carries it (`CARD_MOVES`) — so `Attack` conflicts with a
  Stalker ability but not a Nexus one. Universal commands share a binding `id`, so an edit propagates
  and nothing conflicts with itself.
- The command card is **5×3** (`meta.cardCols/cardRows`); a record's slot is `row*5 + col`.
  Positions are fixed by the game, so the card grid is **read-only** (no `GAME.setSlot`).

## Files (this folder)

- **`game_module_generator.py`** — this game's build CLI (`--build` only; **no in-tool
  `--regen`**). Inlines `module.js` + `data/sc2.json` + `data/sc2_icons.json` into the shell
  `page.html` (via the root `page_assembler`), emitting `site/starcraft2/index.html`, and copies
  `data/icons/` to `site/starcraft2/icons/`.
- **`module.js`** — everything game-specific: the `.SC2Hotkeys` codec, the key-token ↔ VK mapping,
  the naming/grouping/conflict model, the race filter + column categories, and the `GAME.*`
  wiring. Injected at the `/* __GAME_MODULE__ */` marker; wrapped in an IIFE (only registers
  `GAMES.starcraft2`).
- **`data/sc2.json`** — vendored dataset: `units → cards → buttons` (each button's `command`,
  display `name`, default `key`, grid `row`/`col`, `universal` flag, `icon` path), plus a
  `playable` flag (has `HotkeyCategory`/`Mob` — filters out map doodads/destructibles). A later
  mod blanking `HotkeyCategory` to `""` **decommissions** a unit (how `voidmulti` removed the
  Mothership Core in LotV 3.0) even when a stale `Mob` lingers, so an explicitly-empty
  `HotkeyCategory` forces `playable=false`.
- **`data/sc2_icons.json`** — `command → icons/<file>.png` for the on-keyboard ability-icon overlay.
- **`data/icons/*.png`** — the ability icons, converted from the game's `.dds` textures.
- **`data/sc2_defaults.ini`** — flat `command[/unit]=key` dump; a build artifact used only to
  validate the generator against the reference project.

## Regenerating the dataset

Not part of the Python build; only rerun when refreshing from a new patch. Requires the extracted
game files under `data/SC2 data/` (the `core → liberty → libertymulti → swarm → swarmmulti → void
→ voidmulti` multiplayer mod chain + `GameStrings/` + `Icons/`):

```
python3 data/gen_sc2_data.py     # -> data/sc2.json (+ sc2_defaults.ini)
python3 data/gen_sc2_icons.py    # -> data/sc2_icons.json + data/icons/*.png (stdlib DDS->PNG)
python3 game_module_generator.py --build
```

`gen_sc2_data.py` is a clean re-implementation of the dependency-merge + hotkey-resolution process
from [BeedeBdoo/Sc2HotkeyData](https://github.com/BeedeBdoo/Sc2HotkeyData). It was cross-checked
against that project's `output/Defaults.ini` — **298/310 shared default keys match**, and every
remaining discrepancy is the reference lagging the live patch (its extraction predates several
`voidmulti` overrides), verified against the raw game files rather than conformed to. Notably the
reference's Infestor is still the Heart-of-the-Swarm kit (`InfestedTerrans`, no Microbial Shroud),
whereas ours matches the current unit — so the reference is a validation aid, **not** ground truth;
the vendored `data/SC2 data/` extraction wins on conflicts. `gen_sc2_icons.py` includes a
pure-stdlib DDS decoder (uncompressed / DXT1 / DXT5) + PNG encoder — no third-party dependencies.

### Card identity is positional (`<CardLayouts>` is an array too)

A unit's `<CardLayouts>` entries are themselves a **positional array**: a card's identity is its
array index, and `CardId` (`PBl1`, `ZBl2`, ...) is a *property* submenu buttons use to target it.
A base mod declares cards in document order (the main page first, then the `CardId` sub-cards); a
later mod patches one by `index` and often **omits the CardId** — e.g. `voidmulti`'s
`<CardLayouts index="1">` reworks the Probe's `PBl1` "Warp In Structure" sub-card (adding Shield
Battery). Keying a card by CardId-or-index alone splits that patch into a phantom `@1` main page
carrying the sub-card's structures. So `card_position()` resolves index↔CardId through a per-unit
slot map: an explicit `index` names the slot, a **bare** card (no index, no CardId) is the main
card (slot 0 — so a dependency re-stating it, or a unit with several bare cards, all fold onto one
page), and a `CardId` card reuses its slot or appends. An `index=N` patch then lands on whatever
card already occupies slot N (the Probe's `PBl1`, the Drone's `ZBl2`, ...).

### Card-layout merge (the `_apply_card` subtlety)

SC2's `<CardLayouts>` is an **indexed array** of `<LayoutButtons>`, patched across the mod chain:
an explicit `index="N"` sets slot N; a button with no index takes the next free slot; a later mod
overwrites a same-index slot; `removed="1"` clears one. This is how the game applies patches —
e.g. LotV (`voidmulti`) drops a cut ability by overwriting its slot with a new button.

The catch: a **dependency mod re-declaring an existing button is the *same* array element, not a
new one.** So a no-index button whose identity `(Face, AbilCmd)` already sits in the card **reuses
that slot** rather than drifting to `max+1`. Without this, a button restated (no-index) by two mods
lands on two different slots, and a later `index=` override — which targets the single real slot —
removes only one copy, leaking a stale button. Concretely: Infested Terran was cut from the LotV
Infestor by a `voidmulti` `index=7` override, but because both `libertymulti` and `swarm` re-declare
it non-indexed it had drifted onto slots 7 **and** 8, so the slot-8 copy survived on the burrowed
Infestor card until this was fixed.

Identity is `(Face, AbilCmd)`, **not `Face` alone**: a card legitimately carries two same-`Face`
buttons with different `AbilCmd`s (a Factory's two distinct `Cancel`s), and collapsing those would
shift every later slot and make the game's explicit `index=` overrides miss their targets. Genuine
same-`Face` repeats (a unit listing `BurrowDown` a dozen times) are still collapsed for display by
`dedup_faces()`.

The other catch: a `<LayoutButtons index="N" Face="" Type="Undefined"/>` patch is the game's idiom
for **emptying a cell**, and is treated like `removed="1"` — it clears slot N. Crucially the slot's
identity is dropped from the reuse map too, so if a later no-index button re-adds the button that
*used* to sit there, it appends to a fresh slot instead of silently reusing the just-emptied one.
Without this, the blank was a no-op (its `Face=""`/`AbilCmd=""` skipped by the keep-prior merge),
so the reused slot swallowed the restated button and a subsequent `index=` column patch landed on
the wrong cell. Concretely: `swarm` blanks Larva's slot 7 (`liberty`'s Corruptor) then re-adds
Corruptor non-indexed; `voidmulti`'s `index=11` column patch has to shift *that* new slot clear of
Infestor — until this was fixed, Corruptor reused slot 7 and both morphs stacked on the same grid
cell (Raven's `AutoTurret` had the same collision with `Move`).

Because all raw game data is vendored under `data/SC2 data/`, `gen_sc2_data.py`
is deterministic in-container — rerunning it reproduces the committed `sc2.json` exactly.
