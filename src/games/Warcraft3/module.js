// Warcraft III game module -- the WC3 half of the multi-game seam.
//
// Bindings are a single plain-text CustomKeys.txt of `[ABCD]` sections (4-char ability/command
// codes).  This module turns those raw codes into friendly names, groups them by the in-game
// command card they appear on, and flags per-card hotkey conflicts, using the vendored dataset
// in data/wc3.json (derived from jcfieldsdev/warcraft3-hotkey-editor, MIT -- see data/SOURCE.md).
//
// Like the AoE2 module this is injected into the shell's main <script> and wrapped in the IIFE
// below, so its internals stay private; it reaches outward only to register GAMES.warcraft3.
// The engine reaches WC3 only through GAME.* (assembled at the bottom).
//
// One CustomKeys binding can sit on many unit cards, so bindings() emits one *record* per
// (card, command, channel) occurrence, all sharing the binding's `id` and `e` object.  The
// engine already (a) groups records by id so an edit propagates to every occurrence, and
// (b) skips same-id pairs in conflict detection so an ability never clashes with itself across
// cards.  forEachEntry / save iterate the unique underlying bindings (doc.binds).
(function () {

// ===== CustomKeys.txt codec (line-preserving) ====================================
// Plain-text INI: `[ABCD]` sections (4-char codes) with `Key=Value` lines.  Editable
// bindings are Hotkey / Unhotkey / Researchhotkey; everything else (Buttonpos, Tip,
// Modifier, even the stray `Hoktey` typo) is preserved verbatim.  We keep the file as its
// original lines and only rewrite a binding line's *value* when it actually changes, so an
// unedited file round-trips byte-for-byte (blank lines, trailing spaces like `Hotkey= `,
// key order, CRLF/LF, trailing newline all preserved).
var BIND_KEYS = ['Hotkey', 'Unhotkey', 'Researchhotkey'];
var BIND_RE = /^(Hotkey|Unhotkey|Researchhotkey)=(.*)$/;
var MOD_RE = /^Modifier=(.*)$/;
var UNHOTKEYID_RE = /^UnhotkeyId=(.+)$/;   // present => a genuine two-state button (real off-state)
// A section that isn't on any unit card is identified as a global command by its *Command tag
// (control groups, camera, menu, item/hero slots, observer/replay) -- these are the global
// hotkeys the dataset doesn't cover.
var CMD_RE = /^(GameCommand|MenuCommand|CameraCommand|CtrlGroupCommand|ObserverCommand|ReplayCommand)=/;
var CMD_FAMILY = { GameCommand: 'game', MenuCommand: 'menu', CameraCommand: 'camera',
  CtrlGroupCommand: 'ctrl', ObserverCommand: 'observer', ReplayCommand: 'replay' };
var SECTION_RE = /^\[(.*)\]$/;
// command-card position lines (X,Y grid coords): active / hero-learn / two-state off-state buttons
var POS_LINE_RE = /^(Buttonpos|Researchbuttonpos|Unbuttonpos)=\s*(-?\d+)\s*,\s*(-?\d+)/i;
var POS_FIELD = { buttonpos: 'b', researchbuttonpos: 'r', unbuttonpos: 'u' };
var POS_NAME = { b: 'Buttonpos', r: 'Researchbuttonpos', u: 'Unbuttonpos' };
var CARD_COLS = 4;                          // WC3 command card is 4 columns x 3 rows (slot = Y*4 + X)

function bodyOf(line) { return line.charAt(line.length - 1) === '\r' ? line.slice(0, -1) : line; }

function parse(text) {
  var lines = text.split('\n');
  var sections = [];
  var cur = null;
  var pending = '';                                          // `//` comment(s) directly above the next section
  for (var i = 0; i < lines.length; i++) {
    var body = bodyOf(lines[i]);
    if (body.charAt(0) === '/' && body.charAt(1) === '/') {  // comment line -> label for the next section
      var t = body.replace(/^\/+\s*/, '').trim();
      if (t) pending = pending ? pending + ' ' + t : t;
      continue;
    }
    var sm = SECTION_RE.exec(body);
    if (sm) { cur = { code: sm[1], lineIndex: i, binds: {}, modifier: null, modLine: -1, twoState: false, cmd: null, comment: pending, posLines: {}, posOrig: {} }; sections.push(cur); pending = ''; continue; }
    if (body.trim() === '') pending = '';                    // a blank line ends a comment block
    if (!cur) continue;
    var bm = BIND_RE.exec(body);
    if (bm) { cur.binds[bm[1]] = { line: i, value: bm[2] }; continue; }
    var mm = MOD_RE.exec(body);
    if (mm) { cur.modifier = mm[1]; cur.modLine = i; continue; }
    if (UNHOTKEYID_RE.test(body)) { cur.twoState = true; continue; }   // off-state is a real, separate button
    // command-card position lines: capture where each lives + its original slot so the grid drag
    // can rewrite them in place (and revert to byte-exact if dragged back).  X,Y -> slot Y*4+X.
    var pm = POS_LINE_RE.exec(body);
    if (pm) { var pf = POS_FIELD[pm[1].toLowerCase()];
      if (pf) { cur.posLines[pf] = i; var px = parseInt(pm[2], 10), py = parseInt(pm[3], 10);
        cur.posOrig[pf] = (px < 0 || py < 0) ? null : (py * CARD_COLS + px); }
      continue; }
    var cm = CMD_RE.exec(body);
    if (cm && !cur.cmd) cur.cmd = CMD_FAMILY[cm[1]];        // global-command family (if any)
  }
  return { lines: lines, sections: sections };
}

function unparse(ck) { return ck.lines.join('\n'); }

function crOf(line) { return line.charAt(line.length - 1) === '\r' ? '\r' : ''; }

function setValue(ck, lineIndex, key, value) {
  ck.lines[lineIndex] = key + '=' + value + crOf(ck.lines[lineIndex]);
}

// Where a *new* Modifier= line should be inserted in a section: after its last content
// line (so it lands among the section's keys, before the trailing blank -- matching the
// game's own files).  Returns a splice index.
function modInsertPos(ck, sec) {
  var i = sec.lineIndex + 1;
  while (i < ck.lines.length) {
    var body = bodyOf(ck.lines[i]);
    if (body === '' || SECTION_RE.test(body)) break;
    i++;
  }
  return i;
}

// ===== WC3 hotkey value <-> virtual-key code =====================================
// A value is one key per ability level, comma-separated (usually identical, e.g. "A,A,A",
// but can differ like "C,G").  A token is a single letter (A-Z), or a **numeric VK code** for
// everything else -- including the digit KEYS (the '8' key is "56", not "8"), so a bare "8" is
// VK 8 (Backspace), "9" is VK 9 (Tab), etc.  Blank (` `) = unbound.
function vkOfToken(tok) {
  tok = (tok || '').trim();
  if (tok === '') return 0;                                  // unbound
  if (/^[0-9]+$/.test(tok)) return parseInt(tok, 10);       // numeric VK code (incl. single digit)
  var c = tok.charCodeAt(0);
  if (c >= 97 && c <= 122) return c - 32;                    // a-z -> A-Z vk
  return c;                                                  // A-Z / other char -> vk
}
function tokenOfVk(vk) {
  if (!vk) return '';
  if (vk >= 65 && vk <= 90) return String.fromCharCode(vk); // A-Z -> letter
  return String(vk);                                         // digit keys (48-57) + specials -> numeric VK
}
var MOD_FLAGS = {                                            // Modifier= -> ctrl/alt/shift
  'Alt': { alt: 1 }, 'Ctrl': { ctrl: 1 }, 'Shift': { shift: 1 },
  'Ctrl_or_Alt': { ctrl: 1 }
};
// ctrl/alt/shift -> Modifier= value (null = no modifier line).  CustomKeys.txt has no
// real ctrl+alt combo, so ctrl+alt maps back to the game's "Ctrl_or_Alt".  A binding
// loaded as Ctrl_or_Alt round-trips byte-exact unless its flags actually change, because
// save only rewrites entries whose ctrl/alt/shift differ from the originals.
function modString(ctrl, alt, shift) {
  if (ctrl && alt) return 'Ctrl_or_Alt';
  if (ctrl) return 'Ctrl';
  if (alt) return 'Alt';
  if (shift) return 'Shift';
  return null;
}

// ===== dataset (names / grouping / conflicts) ====================================
// data/wc3.json: { units: code -> {name, race, type, commands:[[code,name]...], build?},
// common: {basic,hero,noAttack,tower}, buildCommands, campaignRaces }.  See data/SOURCE.md.
var DATA = null;            // the raw dataset
var DEFAULTS = '';          // bundled default CustomKeys.txt text (the "good defaults")
var NAMESDATA = {};         // code -> name from the SLK tables (data.names), for Miscellaneous labels
var ITEMCAT = {};           // item code -> 'shop'|'powerup'|'campaign' (data.items, from itemdata.slk)
var ICONS = {};             // lower-cased command code -> classic icon basename (data.icons.classic)
var POS = { b: {}, r: {}, u: {} };  // code -> command-card slot (data/positions.json): active / research / off-state
var CAMPAIGN = {};          // unit key -> 1 for campaign-only units (from index.html Campaign lists)
var BUILD_TARGET = {};      // unit key -> 1 for build sub-menus (a unit's `build` target, e.g. cmdbuildhuman)
var UNIT_ORDER = [];        // unit keys, sorted for a sensible grouped list
var UNIT_CARD = {};         // unit key -> [[code, name], ...] (the unit's own commands only)
var UNIT_LABEL = {};        // unit key -> "Race -- Name" (the group / context label)
var COMMON_ORDER = [];      // common-set keys present (basic/hero/noAttack/tower), in display order
var COMMON_LABEL = {        // common-set -> its shared "card" label (shown once, not per unit)
  basic: 'Common — Unit Commands', hero: 'Common — Hero Commands',
  noAttack: 'Common — Non-attacking Commands', tower: 'Common — Tower Commands'
};
// Item purchase hotkeys have no shop card in the base game data (see README).  WC3 templates every
// item with the same fields, so most of these purchase sections are boilerplate the game never uses;
// gen_wc3_items.py (data.items -> ITEMCAT) tags each item by whether its purchase hotkey is ever
// reachable in a match ("melee" = in the drop/marketplace pool or on a shop; "campaign" = quest item;
// "hidden" = ruled out, no shop/pool offers it).  Visible tokens map to a group here.
var ITEM_LABEL = { melee: 'Neutral Items', campaign: 'Campaign Items' };

var RACE_LABEL = {
  human: 'Human', orc: 'Orc', undead: 'Undead', nightelf: 'Night Elf',
  bloodelf: 'Blood Elf', draenei: 'Draenei', demon: 'Demon', naga: 'Naga', neutral: 'Neutral'
};
var RACE_RANK = { human: 0, orc: 1, undead: 2, nightelf: 3, bloodelf: 4, draenei: 5, demon: 6, naga: 7, neutral: 8 };
// a unit's type -> which shared common-command set sits on its card (buildings/other: none)
var COMMON_BY_TYPE = { unit: 'basic', summon: 'basic', hero: 'hero', item: 'hero', noAttack: 'noAttack', tower: 'tower' };

function setData(d) {
  DATA = (d && d.units) ? d : null;
  DEFAULTS = (d && d.defaults) || '';
  NAMESDATA = (d && d.names) || {};
  ITEMCAT = (d && d.items) || {};
  ICONS = (d && d.icons && d.icons.classic) || {};
  POS = (d && d.positions) || { b: {}, r: {}, u: {} };
  CAMPAIGN = {}; ((d && d.campaign) || []).forEach(function (c) { CAMPAIGN[c] = 1; });
  BUILD_TARGET = {};
  UNIT_ORDER = []; UNIT_CARD = {}; UNIT_LABEL = {}; COMMON_ORDER = [];
  if (!DATA) return;
  // Only browsable/playable units (the curated `shown` allowlist), plus the build sub-menus
  // those units open (type 'other' build targets) so build hotkeys stay grouped + conflict-checked.
  var include = {};
  (DATA.shown || Object.keys(DATA.units)).forEach(function (k) { if (DATA.units[k]) include[k] = 1; });
  Object.keys(include).forEach(function (k) {
    var b = DATA.units[k] && DATA.units[k].build;
    if (b && DATA.units[b]) { include[b] = 1; BUILD_TARGET[b] = 1; }
  });
  Object.keys(include).forEach(function (key) {
    var u = DATA.units[key];
    if (!u.commands || !u.commands.length) return;           // nothing of our own to show
    var card = new Map();                                     // dedupe by code (last name wins)
    u.commands.forEach(function (c) { card.set(c[0], c[1]); });
    UNIT_CARD[key] = Array.from(card.entries());
    // The race filter already scopes the list to a race, so a "Human — " prefix on every Human
    // card is noise.  Drop it for the four main (natively selectable) races.  Genuinely neutral
    // units get a trailing "(Neutral)" tag instead of a "Neutral — " prefix, so they read as the
    // unit name and sort/interleave alphabetically by it.  Folded campaign races (Blood Elf,
    // Draenei, Demon, Naga) keep a "Race — " prefix, which disambiguates them under the main
    // race's filter (e.g. "Blood Elf — Dragonhawk Rider" under the Human filter).
    var base = u.name || key;
    UNIT_LABEL[key] = MAIN_RACES[u.race] ? base
      : foldRace(u.race) === 'neutral' ? base + ' (Neutral)'
      : (RACE_LABEL[u.race] || u.race) + ' — ' + base;
    UNIT_ORDER.push(key);
  });
  UNIT_ORDER.sort(function (a, b) {
    var ra = RACE_RANK[DATA.units[a].race], rb = RACE_RANK[DATA.units[b].race];
    if (ra == null) ra = 9; if (rb == null) rb = 9;
    if (ra !== rb) return ra - rb;
    return UNIT_LABEL[a].localeCompare(UNIT_LABEL[b]);
  });
  ['basic', 'hero', 'noAttack', 'tower'].forEach(function (s) {
    if (DATA.common && DATA.common[s] && DATA.common[s].length) COMMON_ORDER.push(s);
  });
}

// ===== doc <-> engine records ====================================================
// The opaque doc is { ck, binds, byCode, name }.  A bind is one editable CustomKeys line
// (a section's Hotkey/Unhotkey/Researchhotkey) carrying mutable engine state; byCode indexes
// them by lower-cased section code (the game matches codes case-insensitively, first wins).
function loadFile(file, _prev) {
  return file.text().then(function (text) {
    var ck = parse(text);
    var binds = [];
    var byCode = {};
    var nextId = 1;
    ck.sections.forEach(function (sec) {
      var mod = MOD_FLAGS[sec.modifier] || {};
      var lc = sec.code.toLowerCase();
      var slot = byCode[lc] || (byCode[lc] = {});
      BIND_KEYS.forEach(function (key) {
        var b = sec.binds[key];
        if (!b) return;
        var tokens = b.value.split(',');
        var vk = vkOfToken(tokens[0]);
        var bind = {
          id: nextId++,            // positive synthetic id (engine remap gates on id>0)
          code: vk, origCode: vk,
          ctrl: mod.ctrl || 0, alt: mod.alt || 0, shift: mod.shift || 0,
          origCtrl: mod.ctrl || 0, origAlt: mod.alt || 0, origShift: mod.shift || 0,
          section: sec.code, codeLc: lc, key: key, line: b.line, levels: tokens.length,
          sec: sec               // section ref: Modifier= is shared by a section's binds
        };
        binds.push(bind);
        if (!slot[key]) slot[key] = bind;   // first section wins on a case-folded collision
      });
    });
    return { ck: ck, binds: binds, byCode: byCode, name: null };   // single file -> replace
  });
}

// Start from the bundled "good defaults" (Sensible Reforged CustomKeys) instead of a picked file.
function loadDefault(prev) {
  if (!DEFAULTS) return Promise.reject(new Error('no bundled defaults'));
  return loadFile({ text: function () { return Promise.resolve(DEFAULTS); } }, prev);
}

function saveDoc(doc, _name) {
  // 1. Rewrite changed binding values in place (line indices stay stable).
  function valueFor(e) {
    var tok = tokenOfVk(e.code);
    return e.levels > 1 ? new Array(e.levels).fill(tok).join(',') : tok;
  }
  doc.binds.forEach(function (e) {
    if (e.code === e.origCode) return;                      // untouched -> leave the line byte-exact
    setValue(doc.ck, e.line, e.key, valueFor(e));
  });
  // 1b. Mirror Researchhotkey -> Hotkey: the research/learn row isn't shown (we treat it as the
  //     ability hotkey), so when a section's Hotkey changes, keep its Researchhotkey line equal.
  //     Only fires on an actual Hotkey edit, so untouched sections stay byte-exact.
  Object.keys(doc.byCode).forEach(function (lc) {
    var slot = doc.byCode[lc], h = slot.Hotkey, r = slot.Researchhotkey;
    if (h && r && h.code !== h.origCode) {
      var tok = tokenOfVk(h.code);
      setValue(doc.ck, r.line, 'Researchhotkey', r.levels > 1 ? new Array(r.levels).fill(tok).join(',') : tok);
    }
  });
  // 2. Apply modifier changes.  Modifier= is per-section, so collect at most one change
  //    per section (the first changed bind wins if a section's binds somehow diverge).
  //    In-place rewrites happen now; line-adds/removes are deferred so indices stay valid.
  var ops = [], seen = {};
  doc.binds.forEach(function (e) {
    if (e.ctrl === e.origCtrl && e.alt === e.origAlt && e.shift === e.origShift) return;
    var sec = e.sec;
    if (seen[sec.lineIndex]) return;
    seen[sec.lineIndex] = 1;
    var str = modString(e.ctrl, e.alt, e.shift);
    if (sec.modLine >= 0) {
      if (str === null) ops.push({ pos: sec.modLine, del: true });    // remove the line
      else setValue(doc.ck, sec.modLine, 'Modifier', str);            // in place
    } else if (str !== null) {                                        // add a new line
      ops.push({ pos: modInsertPos(doc.ck, sec), text: 'Modifier=' + str + crOf(doc.ck.lines[sec.lineIndex]) });
    }
  });
  // 2b. Command-card position (Buttonpos) edits from the grid drag.  Rewrite in place when the
  //     field's line already exists; otherwise queue an insert with the modifier ops so all the
  //     line-adds are spliced together high->low (indices stay valid).  Sections never dragged
  //     have no _posEdit, so they stay byte-exact.
  doc.ck.sections.forEach(function (sec) {
    if (!sec._posEdit) return;
    Object.keys(sec._posEdit).forEach(function (field) {
      var slot = sec._posEdit[field];
      var val = (slot % CARD_COLS) + ',' + Math.floor(slot / CARD_COLS);
      if (sec.posLines[field] != null) setValue(doc.ck, sec.posLines[field], POS_NAME[field], val);
      else ops.push({ pos: modInsertPos(doc.ck, sec), text: POS_NAME[field] + '=' + val + crOf(doc.ck.lines[sec.lineIndex]) });
    });
  });
  ops.sort(function (a, b) { return b.pos - a.pos; });      // high->low so earlier indices stay valid
  ops.forEach(function (op) {
    if (op.del) doc.ck.lines.splice(op.pos, 1);
    else doc.ck.lines.splice(op.pos, 0, op.text);
  });
  var blob = new Blob([unparse(doc.ck)], { type: 'text/plain' });
  return Promise.resolve({ blob: blob, filename: 'CustomKeys.txt',
    note: 'Downloaded CustomKeys.txt — put it in your Warcraft III folder and enable custom keys in-game.' });
}

function comboKey(b) { return b.code + '/' + (b.ctrl ? 1 : 0) + (b.alt ? 1 : 0) + (b.shift ? 1 : 0); }
var KEY_SUFFIX = { Hotkey: '', Unhotkey: ' (Unhotkey)', Researchhotkey: ' (Research)' };

// One record per (card, command).  A command's binding is its Hotkey, falling back to its
// Researchhotkey for passives that only have a learn key; the separate research/learn row is
// dropped -- the game's research hotkey equals the ability hotkey (verified: every section with
// both has them identical), and save() keeps the Researchhotkey line synced to the Hotkey.
function bindings(doc) {
  if (!doc) return [];
  // Dev / no dataset: fall back to a flat list named by raw code (codec still works).
  if (!DATA) {
    return doc.binds.map(function (b) {
      return { e: b, id: b.id, unit: null, set: null, ch: channelOf(b.key), name: b.section + KEY_SUFFIX[b.key],
        group: rawGroup(b.key), hidden: false, chron: false };
    });
  }
  var recs = [], used = {}, onCard = {};
  // mark all of a section's bind lines used (the Researchhotkey is mirrored, never its own row)
  function useSection(slot) { ['Hotkey', 'Unhotkey', 'Researchhotkey'].forEach(function (k) { if (slot[k]) used[slot[k].id] = 1; }); }
  // Skip a binding already emitted onto this same card.  Units that share a display name fold into
  // one group -- most often a building and its `_campaign` twin (e.g. halt / halt_campaign, both
  // "Altar of Kings") -- and every command they share is literally the same CustomKeys line, so
  // without this the generic building commands (Set Rally Point = cmdrally, Cancel = cmdcancelbuild)
  // would show twice on the card.  Keyed by group + binding id, so the same line still appears on
  // genuinely different cards, just once per card.
  function dup(group, id) { var k = group + '\x00' + id; if (onCard[k]) return true; onCard[k] = 1; return false; }
  function emitCommand(unit, set, group, code, name) {
    var lc = code.toLowerCase();
    var slot = doc.byCode[lc];
    if (!slot) return;                                       // no CustomKeys section for this command
    var primary = slot.Hotkey || slot.Researchhotkey;
    if (!primary) return;
    useSection(slot);
    if (dup(group, primary.id)) return;                      // same binding already on this card
    // The game's own strings are the source of truth for the command name (NAMESDATA); the
    // jcfields card label is only a fallback for the few codes the game files don't name.
    name = NAMESDATA[lc] || name;
    // channel = the card the binding lives on: an active command (has a Hotkey) vs a research/
    // learn key (Researchhotkey only).  These sit on different sub-cards, so they never conflict
    // with each other -- e.g. a research key of S must not clash with the active Stop command.
    var ch = slot.Hotkey ? 'active' : 'research';
    recs.push({ e: primary, id: primary.id, unit: unit, set: set, ch: ch, name: name, group: group, hidden: false, chron: false });
    // Unhotkey gets its own "— Off" row only for genuine two-state buttons (Call to Arms / Back
    // to Work etc., flagged by an UnhotkeyId) AND when it differs from the primary.  Most abilities
    // carry a leftover Unhotkey (e.g. Gather) that isn't a real player hotkey -- skip those so they
    // don't show up or raise spurious conflicts.
    if (slot.Unhotkey && slot.Unhotkey.sec.twoState && comboKey(slot.Unhotkey) !== comboKey(primary))
      recs.push({ e: slot.Unhotkey, id: slot.Unhotkey.id, unit: unit, set: set, ch: 'active', name: name + ' — Off', group: group, hidden: false, chron: false });
  }
  // shared common-command cards (shown once each, not repeated under every unit)
  COMMON_ORDER.forEach(function (set) {
    DATA.common[set].forEach(function (c) { emitCommand(null, set, COMMON_LABEL[set], c[0], c[1]); });
  });
  // per-unit command cards (the unit's own abilities)
  UNIT_ORDER.forEach(function (unit) {
    UNIT_CARD[unit].forEach(function (c) { emitCommand(unit, null, UNIT_LABEL[unit], c[0], c[1]); });
  });
  // binds not on any unit card: global commands (control groups, camera, menu, item/hero slots,
  // observer/replay) get their own named groups; item-purchase hotkeys are grouped by kind
  // (data.items); a few stale duplicate rawcodes are hidden; the genuine remainder falls to
  // "Miscellaneous" (neutral build/summon commands with no ownership in the vendored data).
  doc.binds.forEach(function (b) {
    if (used[b.id]) return;
    var suffix = b.key === 'Hotkey' ? '' : KEY_SUFFIX[b.key];
    // A verified-stale duplicate rawcode (checked first, since a couple are also item codes):
    // kept in the file, dropped from the list (hidden:true) so the live carded copy is what's shown.
    if (HIDE[b.codeLc]) { recs.push({ e: b, id: b.id, unit: null, set: null, ch: channelOf(b.key),
      name: nameOf(b) + suffix, group: 'Miscellaneous', hidden: true, chron: false }); return; }
    var g = GLOBAL[b.sec.cmd];
    if (g) { recs.push({ e: b, id: b.id, unit: null, set: g.set, ch: channelOf(b.key),
      name: (GLOBAL_NAMES[b.codeLc] || nameOf(b)) + suffix,
      group: g.group, hidden: false, chron: false }); return; }
    var it = ITEMCAT[b.codeLc];
    // 'hidden' item: a templated purchase hotkey no shop or drop/marketplace pool ever offers, so
    // it can't fire in a match -- drop it from the list (still round-trips on save, like HIDE above).
    if (it === 'hidden') { recs.push({ e: b, id: b.id, unit: null, set: null, ch: channelOf(b.key),
      name: nameOf(b) + suffix, group: 'Miscellaneous', hidden: true, chron: false }); return; }
    // 'melee' (neutral drop/marketplace/shop pool) or 'campaign' -> its own column, not Miscellaneous
    if (it) { recs.push({ e: b, id: b.id, unit: null, set: null, item: it, ch: channelOf(b.key),
      name: nameOf(b) + suffix, group: ITEM_LABEL[it], hidden: false, chron: false }); return; }
    recs.push({ e: b, id: b.id, unit: null, set: null, ch: channelOf(b.key),
      name: nameOf(b) + suffix, group: 'Miscellaneous', hidden: false, chron: false });
  });
  return recs;
}

// A record's ability icon (classic set) for the on-keyboard card overlay -- the engine drops it on
// the key a command is bound to when its card is selected.  Keyed by the binding's command code; the
// URL is relative to the built page (site/warcraft3/index.html -> site/warcraft3/icons/classic/*.png),
// so it works on a static host or opened straight off disk.  Returns null when no icon is mapped
// (e.g. a Miscellaneous rawcode the classic set doesn't cover) -- the engine just skips it.
function iconOf(rec) {
  var code = rec && rec.e && rec.e.codeLc;
  var base = code && ICONS[code];
  return base ? 'icons/classic/' + base + '.png' : null;
}

// A record's slot (0-11) on its unit's in-game 4x3 command card, for the card-grid panel; null when
// this command has no fixed card slot (shop items / mercenaries are laid out from the building's
// sell list at runtime, campaign-only bits aren't mapped) -- the panel just omits it.  A code's slot
// is a property of the ability/unit/upgrade itself (same button wherever it appears), so it doesn't
// depend on which card is shown.
//
// Always use the command's OWN command-card button (`Buttonpos`, POS.b) -- that's where every
// ability/upgrade sits together in-game (e.g. a Paladin's Holy Light / Devotion Aura / Resurrection
// all on the bottom row).  Deliberately NOT `Researchbuttonpos` (POS.r): that's the hero *learn*
// sub-card (a different card, top row), so a passive aura -- whose only binding is its learn key
// (Researchhotkey) -- must still show at its command-card Buttonpos next to the active abilities,
// not at its learn-button slot.  The Unhotkey "— Off" row of a two-state toggle uses the off-state
// button (POS.u).  Fall back to any known slot (a code with only a learn position -- none today).
function slotOf(rec) {
  var code = rec && rec.e && rec.e.codeLc;
  if (!code) return null;
  var s = (rec.e.key === 'Unhotkey') ? POS.u[code] : POS.b[code];
  if (s == null) s = (POS.b[code] != null ? POS.b[code] : POS.r[code]);   // off-state / learn-only fallback
  return s == null ? null : s;
}

// A hero ability's slot on the separate **learn** sub-card (`Researchbuttonpos`, POS.r) -- the
// engine draws this as a second grid beside the command card for heroes.  null when the command
// has no learn button (every non-hero card), so no learn grid shows.
function learnSlotOf(rec) {
  var code = rec && rec.e && rec.e.codeLc;
  var s = code ? POS.r[code] : null;
  return s == null ? null : s;
}

// Move a command to a new card slot (grid drag-and-drop).  `card` is 'command' (the ability's own
// Buttonpos, or Unbuttonpos for an off-state) or 'learn' (its Researchbuttonpos learn button).
// Updates the live slot map so the panel repaints at once, and queues the writeback on the
// command's section (applied by saveDoc).  Dragging back to the file-original slot drops the edit.
function setSlotDoc(doc, rec, slot, card) {
  var e = rec && rec.e; if (!e || !e.codeLc) return;
  var code = e.codeLc;
  var field = (card === 'learn') ? 'r' : (e.key === 'Unhotkey') ? 'u' : 'b';
  POS[field][code] = slot;                          // live update -> card panel + keyboard overlay
  var sec = e.sec; if (!sec) return;
  sec._posEdit = sec._posEdit || {};
  if (sec.posOrig[field] != null && sec.posOrig[field] === slot) delete sec._posEdit[field];  // == file original
  else sec._posEdit[field] = slot;
}

// Every command name comes from the game's own strings files (NAMESDATA = data.names, the real
// localized display names -- see data/gen_wc3_names.py): unit-card commands, common commands,
// globals, and the Miscellaneous tail all resolve through it, so the labels match what the game
// shows.  NAMES here is a small manual-override map for any edge case the game data gets wrong;
// empty for now.
var NAMES = {};

// Orphan/stale ability rawcodes: each is a *second* rawcode for an ability that's already carded
// on a live melee unit under a different code, and is itself used by NO unit in the dataset (verified
// against every unit's command list -- the carded twin is the one the game actually binds).  They
// only clutter the file's tail, so we drop them from the list (the section still round-trips on save,
// untouched; editing the carded copy is what changes the in-game key).  Value = the live carded code
// kept, for the record.  If the dataset ever changes, re-verify before trusting these.
var HIDE = {
  aams: 'aam2', apos: 'aps2', aua2: 'auan', anic: 'ania',   // Anti-magic Shell / Possession / Animate Dead / Incinerate
  ugrm: 'ugar', edcm: 'edoc', edtm: 'edot',                 // Train Gargoyle / Druid of the Claw / Druid of the Talon
  egol: 'aent', aroo: 'aro1', aenc: 'aloa',                 // Entangle Gold Mine / Root / Load
  nalm: 'nalc', nal2: 'nalc', nal3: 'nalc', nrob: 'ntin',   // Summon Alchemist (x3) / Summon Tinker
  ofr2: 'ofir', olig: 'oli2'                                // Orb of Fire / Orb of Lightning (shop-item dupes)
};

// Global-command families -> a display group + conflict scope + which column category they land in.
// The melee-relevant globals share one 'global' scope (so a key reused across them flags) and sit
// in the first (common) category; observer/replay share that column too but form a separate
// 'spectator' conflict scope (they can't clash with in-game play).
var GLOBAL = {
  ctrl:     { set: 'global',    group: 'Control Groups' },
  camera:   { set: 'global',    group: 'Camera' },
  menu:     { set: 'global',    group: 'Menu Commands' },
  game:     { set: 'global',    group: 'Selection & Items' },
  observer: { set: 'spectator', group: 'Observer' },
  replay:   { set: 'spectator', group: 'Replay' }
};
// Friendly names for the global commands (the dataset doesn't cover them).  Derived by matching
// each section's hotkey value to the command name shown in Warcraft III Reforged's default hotkey
// options screens (a one-off transcription; the screenshots are no longer vendored).  Keyed by
// lower-cased section code.
var GLOBAL_NAMES = {
  ctr1: 'Control Group 1', ctr2: 'Control Group 2', ctr3: 'Control Group 3',
  ctr4: 'Control Group 4', ctr5: 'Control Group 5', ctr6: 'Control Group 6',
  ctr7: 'Control Group 7', ctr8: 'Control Group 8', ctr9: 'Control Group 9', ctr0: 'Control Group 10',
  itm1: 'Inventory Slot 1', itm2: 'Inventory Slot 2', itm3: 'Inventory Slot 3',
  itm4: 'Inventory Slot 4', itm5: 'Inventory Slot 5', itm6: 'Inventory Slot 6',
  her1: 'First Hero', her2: 'Second Hero', her3: 'Third Hero',
  sbgp: 'Switch Subgroups', sidw: 'Select Idle Workers', mpng: 'Minimap Ping',
  tmtr: 'Toggle Minimap Terrain', alcm: 'Set Ally Color Mode', tmcd: 'Toggle Minimap Creep Display',
  tfmv: 'Toggle Formation Movement', tahb: 'Toggle Ally Healthbars', tehb: 'Toggle Enemy Healthbars',
  qlog: 'Toggle Quest Log', menu: 'Toggle Game Menu', ally: 'Toggle Allies', chat: 'Toggle Chat',
  qsav: 'Quick Save', mend: 'End Game Menu', mopt: 'Options Menu', msav: 'Save Menu',
  mlod: 'Load Menu', mhlp: 'Help Menu', tmus: 'Toggle Music', tsfx: 'Toggle SFX',
  ctcr: 'Cycle Town Centers', clnt: 'Center on Last Notification', capt: 'Center on Active Portrait',
  zmin: 'Zoom In', zmou: 'Zoom Out', rezm: 'Reset Zoom Level',
  rocl: 'Rotate Camera Left', rocr: 'Rotate Camera Right',
  mvcf: 'Move Camera Forward', mvcb: 'Move Camera Backward', mvcl: 'Move Camera Left', mvcr: 'Move Camera Right',
  ther: 'Toggle Heroes Panel', tsta: 'Toggle Statistics Panel', tpuq: 'Toggle Production/Units Queue',
  tsel: 'Toggle Selection Panel', tmap: 'Toggle Minimap Panel', ttod: 'Toggle Time of Day Indicator',
  tall: 'Toggle All Panels', spqm: 'Production Queue Mode', sulm: 'Units List Mode',
  trpl: 'Toggle Replay Panel', tppl: 'Toggle Pause / Play', ings: 'Increase Game Speed',
  degs: 'Decrease Game Speed', tfow: 'Toggle Fog of War', tauc: 'Toggle Auto Camera'
};

function channelOf(key) { return key === 'Researchhotkey' ? 'research' : 'active'; }
// a name from the section's `//` comment in the file (the game's own default files label most
// sections), capitalised; '' if none.  Used to name commands with no dataset card.
function commentName(b) {
  var c = b.sec && b.sec.comment;
  return c ? c.charAt(0).toUpperCase() + c.slice(1) : '';
}
// display name for a binding with no dataset card: manual override -> SLK name -> file comment ->
// raw code (SLK/override names capitalised).
function nameOf(b) {
  var n = NAMES[b.codeLc] || NAMESDATA[b.codeLc];
  if (n) return n.charAt(0).toUpperCase() + n.slice(1);
  return commentName(b) || b.section;
}
function rawGroup(key) { return key === 'Researchhotkey' ? 'Research Hotkeys' : key === 'Unhotkey' ? 'Unhotkeys' : 'Hotkeys'; }
function forEachEntry(doc, fn) { if (doc) doc.binds.forEach(fn); }
function groupOf(r) { return r.group; }
// conflict scope code: a unit card, or a common-set card (prefixed so the two namespaces never collide)
function context(r) { return r.unit ? 'u:' + r.unit : r.set ? 'c:' + r.set : ''; }
function ctxLabel(ctx) {
  if (ctx && ctx.slice(0, 2) === 'u:') return UNIT_LABEL[ctx.slice(2)] || ctx.slice(2);
  if (ctx && ctx.slice(0, 2) === 'c:') return COMMON_LABEL[ctx.slice(2)] || ctx.slice(2);
  return 'Miscellaneous';
}
// Records clash (engine has already bucketed by key-combo and skipped same-binding pairs) when
// they share a command card.  A common command sits on every unit card of its type, so a common
// record also clashes with any unit-ability record whose unit's type maps to that common set --
// i.e. the shared common cards still conflict against the per-unit cards.  Active and research
// keys live on different sub-cards, so they never conflict across channels.
function classify(ra, rb) {
  if (ra.ch !== rb.ch) return null;                          // active vs research: different cards
  if (ra.unit && rb.unit) return ra.unit === rb.unit ? { sev: 'confirmed' } : null;
  if (ra.set && rb.set) return ra.set === rb.set ? { sev: 'confirmed' } : null;
  var u = ra.unit ? ra : rb.unit ? rb : null;               // the unit-card record (if any)
  var c = ra.set ? ra : rb.set ? rb : null;                 // the common-card record (if any)
  if (u && c && COMMON_BY_TYPE[DATA.units[u.unit].type] === c.set) return { sev: 'confirmed' };
  return null;
}
function recName(r) { return r.name; }

// ===== race filter + category ordering ===========================================
// Race buttons filter the list to a race's cards; generic common commands show under every
// race (the "generic unit commands").  Campaign races fold to their base race; anything else
// (creeps, shops, special) is Neutral.
var MAIN_RACES = { human: 1, orc: 1, undead: 1, nightelf: 1 };
function foldRace(race) {
  var b = (DATA && DATA.campaignRaces && DATA.campaignRaces[race]) || race;
  return MAIN_RACES[b] ? b : 'neutral';
}
var FILTERS = [
  { id: 'human', label: 'Human' }, { id: 'orc', label: 'Orc' },
  { id: 'undead', label: 'Undead' }, { id: 'nightelf', label: 'Night Elf' },
  { id: 'neutral', label: 'Neutral' }
];
function recFilters(r) {
  if (r.set) return ['human', 'orc', 'undead', 'nightelf', 'neutral'];  // generic: every race
  if (r.unit) return [foldRace(DATA.units[r.unit].race)];
  return ['neutral'];                                                    // Other commands
}
// column ordering: cluster by category, then race, then group name.  The engine partitions this
// order into contiguous columns.  Category order: common -> heroes -> units -> buildings ->
// campaign (units that only appear in campaign, not melee; the Miscellaneous catch-all shares this
// column group).  Campaign-only units go to the campaign bucket regardless of their unit type, so
// the melee categories are melee-relevant.  The `other` type is real melee units the dataset
// didn't classify (e.g. the Gargoyle) -> Units; build sub-menus (also type `other`) are handled
// separately in catOf and land with Buildings.
var CAT_RANK = { hero: 1, unit: 2, summon: 2, item: 2, noAttack: 2, building: 3, tower: 3, other: 2 };
var CAT_CAMPAIGN = 4;   // Miscellaneous shares CAT_CAMPAIGN (the melee campaign column group)
var CAT_ITEMS = 5;      // shop / powerup item-purchase hotkeys (campaign items go to CAT_CAMPAIGN)
// set-scope -> column category. Common cards, the melee globals, and the spectator scope
// (observer/replay) all share the first (common) category so the global hotkeys stay in one
// column instead of stranding observer/replay in a sparse column of their own. Spectator keeps
// its separate *conflict* scope (see context()); this only controls column placement.
var SET_CAT = { basic: 0, hero: 0, noAttack: 0, tower: 0, global: 0, spectator: 0 };
function pad2(n) { return (n < 10 ? '0' : '') + n; }
function catOf(r) {
  if (r.item) return r.item === 'campaign' ? CAT_CAMPAIGN : CAT_ITEMS;  // campaign items join the campaign column
  if (r.set) return SET_CAT[r.set] != null ? SET_CAT[r.set] : 0;
  if (r.unit) {
    if (CAMPAIGN[r.unit]) return CAT_CAMPAIGN;               // campaign-only unit -> campaign column
    // A build sub-menu is a melee Buildings card only for the four main races; the campaign races'
    // build menus (Blood Elf / Draenei / Naga) are campaign content -> campaign column.
    if (BUILD_TARGET[r.unit]) return MAIN_RACES[DATA.units[r.unit].race] ? CAT_RANK.building : CAT_CAMPAIGN;
    return CAT_RANK[DATA.units[r.unit].type] || CAT_CAMPAIGN;
  }
  return CAT_CAMPAIGN;                                        // Miscellaneous -> campaign's column group
}
function groupKey(r) {
  // within a category, cards are ordered alphabetically by name; the only non-alphabetical bit is
  // the Common column's curated tier order: shared common cards (0), then the melee globals (1),
  // then the spectator globals (2, so observer/replay trail them).  Unit cards carry tier 0, so
  // they simply sort by name -- races interleave alphabetically instead of clustering by race
  // (a specific race filter shows one race anyway; this only affects the "All" view).
  var tier = r.set ? (r.set === 'spectator' ? 2 : r.set === 'global' ? 1 : 0) : 0;
  return pad2(catOf(r)) + '|' + tier + '|' + r.group;   // category | tier | name
}
// the strict-column category id (engine gives each category its own column(s)); matches the
// leading field of groupKey so categories stay contiguous in the sorted order.
function groupCategory(r) { return pad2(catOf(r)); }
// human-readable title the engine prints atop each column, keyed by the groupCategory id
var CAT_TITLE = { '00': 'Common', '01': 'Heroes', '02': 'Units', '03': 'Buildings', '04': 'Campaign', '05': 'Items' };
function categoryTitle(id) { return CAT_TITLE[id] || ''; }

function fileStatus(doc) {
  return doc ? '<span class="chip ok">✓ CustomKeys.txt</span>'
             : '<span class="chip need">⬆ load CustomKeys.txt</span>';
}

// ===== register this game + wire it into the engine's GAME interface =============
GAMES.warcraft3 = {
  meta: {
    name: 'Warcraft III',
    blurb: 'Works with classic Warcraft III CustomKeys.txt.',
    fileLabel: 'Load CustomKeys.txt',
    defaultsLabel: 'Load defaults',
    filterLabel: 'Race:',
    fileAccept: '.txt',
    multiple: false,
    usesProfileName: false,       // the download is always CustomKeys.txt
    hasChroniclesToggle: false,
    cardCols: 4, cardRows: 3,     // WC3 command card geometry for the card-grid panel (4 wide x 3 tall)
    pathHelpTitle: 'Where Warcraft III custom hotkeys go (click for details)',
    pathHelp:
      '<p><b>To get started:</b> load your <code>CustomKeys.txt</code>.</p>'
      + '<p><b>Where it lives:</b> your Warcraft III folder — for Reforged, '
      + '<code>Documents\\Warcraft III\\CustomKeys.txt</code>.</p>'
      + '<p>Edit hotkeys here, download the file, and put it back. Enable <i>Custom Hotkeys</i> '
      + 'in the game\'s gameplay options for it to take effect.</p>',
    placeholder: 'Load your <code>CustomKeys.txt</code> to view and edit Warcraft III hotkeys, '
      + 'or click <b>Load defaults</b> to start from a clean, conflict-free default set.',
    applyNote: 'Save CustomKeys.txt back into your Warcraft III folder, then enable custom '
      + 'hotkeys in the game\'s options.'
  },
  // file format: opaque doc in, packaged download out
  codec: { load: loadFile, loadDefault: loadDefault, save: saveDoc, parse: parse, unparse: unparse, setValue: setValue },
  // WC3 has no extra mouse buttons or VK labels (the engine's letter/number VK table suffices)
  input: { vkLabels: {}, mouseButtons: [] },
  setData: setData,
  fileStatus: fileStatus,
  bindings: bindings,
  forEachEntry: forEachEntry,
  groupOf: groupOf,
  context: context,
  classify: classify,
  recName: recName,
  icon: iconOf,              // ability-card icon overlaid on the keyboard when a card is selected
  slot: slotOf,              // command-card grid slot (0-11 on the 4x3 card) for the card-grid panel, or null
  learnSlot: learnSlotOf,    // hero learn sub-card slot (Researchbuttonpos) -> a 2nd grid beside the command card
  setSlot: setSlotDoc,       // move a command to a new card slot (grid drag) -> Buttonpos writeback
  baseName: function (r) { return r && r.name ? r.name : ''; },
  ctxLabel: ctxLabel,
  filters: FILTERS,          // race filter buttons (engine shows them; AoE2 omits -> no bar)
  recFilters: recFilters,    // which race(s) a record belongs to
  groupKey: groupKey,        // column/category ordering key
  groupCategory: groupCategory,  // strict-column category id (each category gets its own columns)
  categoryTitle: categoryTitle   // display title the engine prints atop each column of a category
};

})();
