// AoE2:DE game module -- the per-game half of the multi-game seam.
//
// page.html is the generic engine/UI shell; everything AoE2-specific (the .hkp
// codec, command naming/grouping, and the civ-aware conflict rules) lives here and
// is wired into the engine through the GAMES.aoe2 / GAME interface at the bottom of
// this file.  game_module_generator.py --build injects this file (and the json data)
// into the shell to produce the self-contained site/aoe2/index.html.
//
// This file is injected inside the shell's main <script> and wrapped in the IIFE below,
// so its internals (the codec, dataset lookups, naming/grouping, conflict rules) stay
// private instead of leaking into the page's global scope.  It reaches outward only to
// read engine globals it needs (e.g. `state`) and to register itself as GAMES.aoe2; the
// engine reaches AoE2 code only through GAME.* (assembled at the bottom).  Keep the codec
// byte-for-byte in step with the Python oracle hkp_parser.py.
(function () {

// ===== .hkp parser: ported from hkp_parser.py, verified byte-exact vs Python =====
// (inflate/deflate via native deflate-raw streams; struct via DataView; STORE zip)
const hkp = (() => {
const enc = s => Uint8Array.from(s, c => c.charCodeAt(0));

const GROUP_HEADER_MAGIC = 0x00100a60;
const S = {
  BASE_BEGIN: enc('baseHotkeysBegin'),
  BASE_END: enc('baseHotkeysEnd'),
  SHARED_BEGIN: enc('sharedHotkeyGroupsBegin'),
  SHARED_END: enc('sharedHotkeyGroupsEnd'),
  HANDLER_BEGIN: enc('HandlerBaseGroupBegin'),
  HANDLER_END: enc('HandlerBaseGroupEnd'),
  GUARD: enc('GroupHeaderGuard'),
  ADD_BEGIN: enc('additionalHotkeysBegin'),
  ADD_END: enc('additionalHotkeysEnd'),
  DET_BEGIN: enc('detachedHotkeyGroupsBegin'),
  DET_END: enc('detachedHotkeyGroupsEnd'),
  DG_BEGIN: enc('detachedHotkeysGroupBegin'),
  DG_END: enc('detachedHotkeysGroupEnd'),
};
const SECTIONS = [
  [enc('allUnitCommandHotkeysBegin'), enc('allUnitCommandHotkeysEnd')],
  [enc('allGameCommandHotkeysBegin'), enc('allGameCommandHotkeysEnd')],
  [enc('allCycleCommandHotkeysBegin'), enc('allCycleCommandHotkeysEnd')],
];

class ParseError extends Error {}

class Reader {
  constructor(data) {
    this.data = data;
    this.dv = new DataView(data.buffer, data.byteOffset, data.byteLength);
    this.pos = 0;
  }
  u32() { const v = this.dv.getUint32(this.pos, true); this.pos += 4; return v >>> 0; }
  f32() { const v = this.dv.getFloat32(this.pos, true); this.pos += 4; return v; }
  peek(lit) {
    if (this.pos + lit.length > this.data.length) return false;
    for (let i = 0; i < lit.length; i++) if (this.data[this.pos + i] !== lit[i]) return false;
    return true;
  }
  lit(l) {
    if (!this.peek(l)) throw new ParseError('expected ' + String.fromCharCode(...l) + ' at offset ' + this.pos);
    this.pos += l.length;
  }
  entry() {
    const code = this.dv.getUint32(this.pos, true);
    const sid = this.dv.getInt32(this.pos + 4, true);
    const ctrl = this.data[this.pos + 8], alt = this.data[this.pos + 9],
          shift = this.data[this.pos + 10], pad = this.data[this.pos + 11];
    this.pos += 12;
    return { code: code >>> 0, id: sid, ctrl, alt, shift, pad };
  }
  wrapped_entry() {
    this.lit(S.HANDLER_BEGIN);
    if (this.u32() !== GROUP_HEADER_MAGIC) throw new ParseError('bad group header magic at ' + (this.pos - 4));
    this.lit(S.GUARD);
    const e = this.entry();
    this.lit(S.HANDLER_END);
    return e;
  }
  menu(wrapped) {
    const count = this.u32();
    if (count > 100000) throw new ParseError('implausible count ' + count + ' at ' + (this.pos - 4));
    const out = [];
    for (let i = 0; i < count; i++) out.push(wrapped ? this.wrapped_entry() : this.entry());
    return out;
  }
  eof() { return this.pos === this.data.length; }
}

function parse_shared(r, wrapped) {
  const num = r.u32();
  if (wrapped) { r.lit(S.BASE_BEGIN); r.lit(S.SHARED_BEGIN); }
  const menus = [];
  for (let i = 0; i < num; i++) menus.push(r.menu(wrapped));
  let empty = 0;
  if (wrapped) {
    while (!r.peek(S.SHARED_END)) { if (r.u32() !== 0) throw new ParseError('expected empty menu slot at ' + (r.pos - 4)); empty++; }
    r.lit(S.SHARED_END); r.lit(S.BASE_END);
  } else {
    while (!r.eof()) { if (r.u32() !== 0) throw new ParseError('expected empty menu slot at ' + (r.pos - 4)); empty++; }
  }
  return { kind: 'shared', menus, empty_slots: empty };
}

function parse_base(r, wrapped) {
  const sections = [];
  if (wrapped) {
    r.lit(S.ADD_BEGIN);
    for (const [b, e] of SECTIONS) { r.lit(b); sections.push(r.menu(true)); r.lit(e); }
    r.lit(S.DET_BEGIN);
  } else {
    for (let i = 0; i < SECTIONS.length; i++) sections.push(r.menu(false));
  }
  const num = r.u32();
  const groups = [];
  for (let i = 0; i < num; i++) {
    if (wrapped) {
      const count = r.u32();
      r.lit(S.DG_BEGIN);
      const g = [];
      for (let j = 0; j < count; j++) g.push(r.wrapped_entry());
      r.lit(S.DG_END);
      groups.push(g);
    } else {
      groups.push(r.menu(false));
    }
  }
  if (wrapped) { r.lit(S.DET_END); r.lit(S.ADD_END); }
  return {
    kind: 'base',
    unit_commands: sections[0], game_commands: sections[1], cycle_commands: sections[2],
    detached_groups: groups,
  };
}

function parse(data) {
  let r = new Reader(data);
  const version = r.f32();
  let info;
  if (r.peek(S.ADD_BEGIN)) {
    info = parse_base(r, true);
  } else if (data.length >= 8 + S.BASE_BEGIN.length &&
             (() => { for (let i = 0; i < S.BASE_BEGIN.length; i++) if (data[8 + i] !== S.BASE_BEGIN[i]) return false; return true; })()) {
    info = parse_shared(r, true);
  } else {
    info = null;
    for (const fn of [parse_shared, parse_base]) {
      r = new Reader(data); r.f32();
      try { info = fn(r, false); break; }
      catch (e) { if (e instanceof ParseError || e instanceof RangeError) info = null; else throw e; }
    }
    if (info === null) throw new ParseError('unrecognized .hkp layout');
  }
  if (!r.eof()) throw new ParseError('trailing data at offset ' + r.pos + ' of ' + r.data.length);
  info.version = Math.round(version * 100) / 100;
  info.wrapped = version >= 4.25;
  return info;
}

// --- writing -----------------------------------------------------------
function concat(arrs) {
  let len = 0; for (const a of arrs) len += a.length;
  const out = new Uint8Array(len);
  let o = 0; for (const a of arrs) { out.set(a, o); o += a.length; }
  return out;
}
function u32le(v) { const b = new Uint8Array(4); new DataView(b.buffer).setUint32(0, v >>> 0, true); return b; }
function f32le(v) { const b = new Uint8Array(4); new DataView(b.buffer).setFloat32(0, v, true); return b; }
function entryBytes(e) {
  const b = new Uint8Array(12), dv = new DataView(b.buffer);
  dv.setUint32(0, e.code >>> 0, true);
  dv.setInt32(4, e.id | 0, true);
  b[8] = e.ctrl & 255; b[9] = e.alt & 255; b[10] = e.shift & 255; b[11] = (e.pad || 0) & 255;
  return b;
}

function unparse(info) {
  const wrapped = info.wrapped;
  const chunks = [f32le(info.version)];
  const writeEntry = (e, w) => {
    if (w) chunks.push(S.HANDLER_BEGIN, u32le(GROUP_HEADER_MAGIC), S.GUARD, entryBytes(e), S.HANDLER_END);
    else chunks.push(entryBytes(e));
  };
  const writeMenu = (menu, w) => { chunks.push(u32le(menu.length)); for (const e of menu) writeEntry(e, w); };

  if (info.kind === 'shared') {
    chunks.push(u32le(info.menus.length));
    if (wrapped) chunks.push(S.BASE_BEGIN, S.SHARED_BEGIN);
    for (const m of info.menus) writeMenu(m, wrapped);
    for (let i = 0; i < info.empty_slots; i++) chunks.push(u32le(0));
    if (wrapped) chunks.push(S.SHARED_END, S.BASE_END);
  } else {
    const sections = [info.unit_commands, info.game_commands, info.cycle_commands];
    if (wrapped) {
      chunks.push(S.ADD_BEGIN);
      for (let i = 0; i < SECTIONS.length; i++) { chunks.push(SECTIONS[i][0]); writeMenu(sections[i], true); chunks.push(SECTIONS[i][1]); }
      chunks.push(S.DET_BEGIN, u32le(info.detached_groups.length));
      for (const g of info.detached_groups) {
        chunks.push(u32le(g.length), S.DG_BEGIN);
        for (const e of g) writeEntry(e, true);
        chunks.push(S.DG_END);
      }
      chunks.push(S.DET_END, S.ADD_END);
    } else {
      for (const m of sections) writeMenu(m, false);
      chunks.push(u32le(info.detached_groups.length));
      for (const g of info.detached_groups) writeMenu(g, false);
    }
  }
  return concat(chunks);
}

// --- raw deflate (native browser/Node streams) -------------------------
async function inflateRaw(u8) {
  const ds = new DecompressionStream('deflate-raw');
  const ab = await new Response(new Blob([u8]).stream().pipeThrough(ds)).arrayBuffer();
  return new Uint8Array(ab);
}
async function deflateRaw(u8) {
  const cs = new CompressionStream('deflate-raw');
  const ab = await new Response(new Blob([u8]).stream().pipeThrough(cs)).arrayBuffer();
  return new Uint8Array(ab);
}

// --- zip (STORE; .hkp payload is already deflate-compressed) ------------
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0; }
  return t;
})();
function crc32(u8) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < u8.length; i++) c = CRC_TABLE[(c ^ u8[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
function u16le(v) { const b = new Uint8Array(2); new DataView(b.buffer).setUint16(0, v, true); return b; }
function zipStore(entries) {
  const te = new TextEncoder();
  const parts = [], central = [];
  let offset = 0;
  for (const [nm, data] of entries) {
    const name = te.encode(nm);
    const crc = crc32(data);
    const lh = concat([u32le(0x04034b50), u16le(20), u16le(0x0800), u16le(0), u16le(0), u16le(0),
      u32le(crc), u32le(data.length), u32le(data.length), u16le(name.length), u16le(0), name]);
    parts.push(lh, data);
    central.push(concat([u32le(0x02014b50), u16le(20), u16le(20), u16le(0x0800), u16le(0), u16le(0), u16le(0),
      u32le(crc), u32le(data.length), u32le(data.length), u16le(name.length), u16le(0), u16le(0), u16le(0), u16le(0),
      u32le(0), u32le(offset), name]));
    offset += lh.length + data.length;
  }
  const cdStart = offset;
  let cdSize = 0;
  for (const c of central) { parts.push(c); cdSize += c.length; }
  parts.push(concat([u32le(0x06054b50), u16le(0), u16le(0), u16le(entries.length), u16le(entries.length),
    u32le(cdSize), u32le(cdStart), u16le(0)]));
  return concat(parts);
}
async function buildZipBytes(name, profile, base) {
  name = (name || 'Hotkeys').trim() || 'Hotkeys';
  const entries = [];
  if (profile) entries.push([name + '.hkp', await deflateRaw(unparse(profile))]);
  if (base) entries.push([name + '/Base.hkp', await deflateRaw(unparse(base))]);
  return zipStore(entries);
}

async function buildZip(name, profile, base) {
  return new Blob([await buildZipBytes(name, profile, base)], { type: 'application/zip' });
}
return { parse, unparse, inflateRaw, deflateRaw, buildZipBytes, buildZip, crc32, ParseError };
})();

// ---- dataset (filled by GAME.setData from the inlined/ fetched json) ----
let strings = {};            // hotkey string id -> display name
let CIV = null;              // {idToCivs:{id:[civs]}, units:Set of unit ids}
let cardData = null;         // our own {byId:{id:[group,ctx]}, chronicles, hidden} mapping
let chronIds = new Set();    // command ids known to be Chronicles content
let hiddenIds = new Set();   // command ids always hidden (e.g. the redundant generic "Build")
function isChronName(n){ return /army tent|alexander.s army|\(campaign only\)/i.test(n||''); }

// ---- command naming ----
function baseName(id){ return strings[id] || ('id '+id); }
function recName(r){
  let n=baseName(r.id);
  if(r.occ>1) n+=' ('+r.occ+')';          // alternate binding of the same command
  return n;
}

// ---- file menus + editable records ----
// ---- file menus ----
function menusOf(info){
  if(!info) return [];
  if(info.kind==='shared') return info.menus.map((m,i)=>['Menu '+(i+1), m]);
  const out=[['Unit commands',info.unit_commands],
            ['Game commands',info.game_commands],
            ['Cycle commands',info.cycle_commands]];
  info.detached_groups.forEach((g,i)=>out.push(['Group '+(i+1), g]));
  return out;
}
function forEachEntry(fn){
  [state.base, state.profile].forEach(info=>
    menusOf(info).forEach(([,menu])=>menu.forEach(fn)));
}
function buildEntries(){
  const list=[]; const occ=new Map();
  [['b',state.base],['p',state.profile]].forEach(([tag,info])=>{
    menusOf(info).forEach(([label,menu])=>{
      menu.forEach(e=>{
        if(e.id<=0) return;
        const n=(occ.get(e.id)||0)+1; occ.set(e.id,n);
        list.push({e:e, id:e.id, occ:n, src:tag+'|'+label,
                   chron: chronIds.has(e.id) || isChronName(strings[e.id]),
                   hidden: hiddenIds.has(e.id)});
      });
    });
  });
  return list;
}
const MENU_NAMES={'p|Menu 1':'Misc','p|Menu 2':'Game & Chat','p|Menu 3':'Idle Units',
  'p|Menu 4':'Control Groups','p|Menu 5':'Camera','p|Menu 6':'Replay','p|Menu 7':'Unit Stances',
  'p|Menu 8':'Zoom','p|Menu 9':'Gates'};
// built-in fallback grouping, read from the file's own structure (merges into the
// matching curated group names where they exist, e.g. newer "Select all X" cmds)
function structureGroupName(r){
  const s=r.src;
  if(s==='b|Game commands') return 'Select Commands';
  if(s==='b|Cycle commands') return 'Go-To Commands';
  if(s==='b|Unit commands') return 'Unit Commands';
  if(MENU_NAMES[s]) return MENU_NAMES[s];
  return 'Other Commands';
}
// the real building/command-card name (our curated card_data), falling back to
// the file's built-in section/menu name for globals and unlabelled entries
function groupNameOf(r){
  const e=cardData && cardData.byId && cardData.byId[r.id];
  return e ? e[0] : structureGroupName(r);
}

// ---- civ-aware conflict rules ----
// Command slots that are mutually exclusive by civ — a civ fields at most one, so they
// can never both be active even in the same card. Used only where the civ dataset can't
// express it (a generic "Unique X" slot has no real unit name to look up). By command id
// (stable per game version).  [[explicit-mutex-vs-civ-data]]
const MUTEX_GROUPS=[
  [19053,19358],          // generic Unique Warships  <->  Thirisadai (Bengalis')
  [19136,19330,19354],    // Go to  Donjon / Krepost / Mule Cart   — civ-exclusive buildings
  [19137,19019,19159],    // Select all  Donjons / Kreposts / Mule Carts  — same
  [19143,19060],          // Xolotl Warrior  <->  Scout Cavalry / Hussar  — civ-exclusive: the
                          // Xolotl is trained only by American civs (no Scout line) from
                          // captured/scenario Stables; Scout-line civs never field the Xolotl,
                          // so the two never share a Stable card. (Xolotl has no civ node, so
                          // the name-keyed civ dataset can't resolve this on its own.)
];
// Generic "unique" command slots that EVERY civ has on a card (Castle's unique unit + its
// three unique techs). Their names are civ-generic, so the name-keyed civ dataset can't
// resolve them (civsForId is null) and a same-card pair would fall through to a soft
// 'possible'. But all civs always have all of them, so two on one combo definitely clash.
// Same-card pairs among these are forced to 'confirmed'.  [[explicit-mutex-vs-civ-data]]
const UNIVERSAL_SLOTS=new Set([
  19080,   // Tech: Elite Unique Unit
  19081,   // Tech: Unique Castle Technology
  19082,   // Tech: Unique Imperial Technology
  19322,   // Unique Unit (Castle)
  19187,   // Unique Unit (Donjon)
]);
const mutexOf=new Map();
MUTEX_GROUPS.forEach((g,i)=>g.forEach(id=>mutexOf.set(id,i)));
function sameMutex(a,b){ return mutexOf.has(a) && mutexOf.get(a)===mutexOf.get(b); }
// Pairs that are technically co-bindable but practically a non-issue: shown as an
// informational note (override tier — blue ⓘ, no key ring, not counted as a clash) with
// a custom message, instead of a civ "possible" flag.  [[explicit-mutex-vs-civ-data]]
const NOTE_PAIRS=[
  { a:19125, b:19070,     // Infantry Unique Units  vs  Eagle Warrior / Fire Lancer
    msg:'Only clashes if you somehow field both at once — e.g. teamed with Italians '
       +'(Condottiero) or via a conversion. No civ has both normally, so it usually '
       +'doesn’t matter.' },
];
const noteOf=new Map();
NOTE_PAIRS.forEach(p=>noteOf.set(Math.min(p.a,p.b)+'|'+Math.max(p.a,p.b), p.msg));
function noteFor(a,b){ return noteOf.get(Math.min(a,b)+'|'+Math.max(a,b)) || null; }
// Command ids that can never clash with anything — they live in their own isolated sub-mode,
// not active at the same time as ordinary bindings. e.g. Remove Gather Point is only reachable
// after Set Gather Point is pressed, so it's effectively its own group.  [[explicit-mutex-vs-civ-data]]
const ISOLATED_IDS=new Set([
  19121,   // Remove Gather Point (only usable once setting a gather point)
]);
// Civ availability is keyed by command id (the .hkp id), precomputed at regen time,
// so the runtime needs no name matching.
function civsForId(id){ return CIV ? (CIV.idToCivs[id]||null) : null; }
function isUnitId(id){ return CIV ? CIV.units.has(id) : false; }
// conflict context comes from card_data.byId[id][1] (G/R/U:type/B:tab/D:card/CAMP)
function recContext(r){
  const e=cardData && cardData.byId && cardData.byId[r.id];
  return e ? e[1] : ('Z|'+r.src);     // unknown -> isolated (no conflicts)
}
// Decide if two same-combo commands clash, given their contexts.  Different unit
// types / build tabs / building cards are mutually exclusive (no clash); 'any'
// overlaps everything in its layer; same building card -> civ-availability check.
function uTypesOverlap(ta, tb){
  if(ta===tb) return true;
  if(ta==='any'||tb==='any') return true;        // 'any' = every unit type
  if(ta==='nonsiege') return tb!=='siege';       // every type except siege (e.g. Garrison)
  if(tb==='nonsiege') return ta!=='siege';
  return false;                                  // two distinct unit types never coexist
}
function ctxClassify(ra, rb){
  if(ISOLATED_IDS.has(ra.id) || ISOLATED_IDS.has(rb.id)) return null;   // isolated sub-mode, never clashes
  if(sameMutex(ra.id, rb.id)) return null;   // civ-exclusive alternative slots never clash
  const note=noteFor(ra.id, rb.id);
  if(note) return {sev:'override', note:note};   // edge-case caution, not a real conflict
  const ca=recContext(ra), cb=recContext(rb);
  if(ca==='G'&&cb==='G') return {sev:'confirmed'};
  if(ca==='R'&&cb==='R') return {sev:'confirmed'};
  if(ca==='R'||cb==='R') return null;
  if(ca==='G'||cb==='G') return {sev:'override'};      // global shadowed by a card/selection
  const la=ca[0], lb=cb[0];
  if(la!==lb) return null;                              // different selection layers
  const ta=ca.slice(2), tb=cb.slice(2);
  if(la==='U') return uTypesOverlap(ta,tb) ? {sev:'confirmed'} : null;
  if(la==='B'){                                               // villager build menu
    if(ca!==cb) return null;                                  // eco vs mil tab — mutually exclusive
    const fa=civsForId(ra.id), fb=civsForId(rb.id);           // same tab -> civ check. Civ-exclusive
    if(fa && fb){ const ov=fa.filter(c=>fb.indexOf(c)>=0);    // buildings (Feitoria/Settlement/Donjon/
      if(!ov.length) return null;                             // Krepost/Mule Cart…) never coexist -> no
      return {sev:'confirmed', civs:ov}; }                    // clash; Settlement replaces Mill/Lumber/Mining
    return {sev:'confirmed'};                                 // can't civ-verify (universal/nav) -> flag
  }
  if(la==='T') return ca===cb ? {sev:'confirmed'} : null;     // garrisons/transports
  if(la==='D'){
    if(ta==='any'||tb==='any') return {sev:'confirmed'};      // a building-wide command
    if(ta!==tb) return null;                                  // different building cards
    if(UNIVERSAL_SLOTS.has(ra.id)&&UNIVERSAL_SLOTS.has(rb.id))
      return {sev:'confirmed'};                               // every civ has these -> always clash
    const fa=civsForId(ra.id), fb=civsForId(rb.id);           // same card -> civ check
    if(fa && fb){ const ov=fa.filter(c=>fb.indexOf(c)>=0);
      if(!ov.length) return null;                             // civ-exclusive -> not a clash
      return (isUnitId(ra.id)&&isUnitId(rb.id)) ? {sev:'confirmed',civs:ov} : {sev:'possible',civs:ov}; }
    return {sev:'possible'};                                  // same card, can't civ-verify -> flag for review
  }
  return null;
}
// human-readable name for a conflict context code (G / R / U:type / B:tab / D:card / T:type)
function ctxLabel(ctx){
  if(!ctx) return '';
  if(ctx==='G') return 'Global — active everywhere';
  if(ctx==='R') return 'Replay controls';
  if(ctx.indexOf(':')<0) return ctx[0]==='Z' ? 'Ungrouped command' : ctx;
  const layer=ctx[0], rest=ctx.slice(2);
  if(layer==='U') return 'Selected '+rest+' unit';
  if(layer==='B') return 'Villager build menu — '+(rest==='eco'?'Economy':rest==='mil'?'Military':rest);
  if(layer==='D') return rest+' — command card';
  if(layer==='T') return 'Garrison / transport — '+rest;
  return rest||ctx;
}

// ===== register this game + wire its implementations into the engine's GAME interface =====
// Self-registers under its slug (the shell's GAMES starts empty); the engine then picks the
// active GAME from window.GAME_DATA.game.
GAMES.aoe2 = {
  // game identity + the shell's game-specific copy (the engine's applyMeta() paints
  // these into the header/empty-state so page.html carries no AoE2 text itself)
  meta: {
    name: 'AoE2:DE',
    blurb: 'Works with AoE2:DE (build 177723).',
    fileLabel: 'Load .hkp files',
    fileAccept: '.hkp',
    multiple: true,
    hasChroniclesToggle: true,
    pathHelpTitle: 'Where AoE2:DE hotkeys go (click for details)',
    pathHelp:
      '<p><b>To get started:</b> load the two files for your current hotkey layout/profile.</p>'
      + '<p><b>Hotkey folder:</b> AoE2:DE hotkeys live in your profile folder at</p>'
      + '<p><code>C:\\Users\\&lt;you&gt;\\Games\\Age of Empires 2 DE\\&lt;Steam ID&gt;\\profile</code></p>'
      + '<p>Each profile is <b>two files</b> — <code>&lt;Name&gt;.hkp</code> at the profile root, '
      + 'and <code>&lt;Name&gt;\\Base.hkp</code> inside a subfolder of the same name.</p>'
      + '<p>The download will provide both files in that structure; extract them and then copy '
      + 'them back to your profile folder (after backing up the profile and deleting it in game '
      + 'if you play on through Steam).</p>',
    placeholder:
      'Load both files of a profile:<br>'
      + '<code>&lt;Name&gt;.hkp</code> and that profile\'s <code>Base.hkp</code> '
      + '(from <code>…/profile/&lt;Name&gt;/Base.hkp</code>).',
    applyNote:
      'Apply hotkeys by placing the files in your AoE2 profile folder. On Steam, delete the '
      + 'hotkey layout in-game first so Steam removes its cloud copy.',
  },
  // file format: bytes <-> parsed doc, and download packaging
  codec: { parse:hkp.parse, unparse:hkp.unparse, inflate:hkp.inflateRaw,
           deflate:hkp.deflateRaw, buildZip:hkp.buildZip, buildZipBytes:hkp.buildZipBytes },
  // game-specific input: extra VK labels + the on-screen mouse buttons
  input: {
    vkLabels: { 251:'Extra Btn 2', 252:'Extra Btn 1', 253:'Middle Btn',
                254:'Wheel Down', 255:'Wheel Up' },
    mouseButtons: [
      { vk:255, label:'▲', cls:'m-wu',  title:'Wheel Up' },
      { vk:253, label:'●', cls:'m-mid', title:'Middle Button' },
      { vk:254, label:'▼', cls:'m-wd',  title:'Wheel Down' },
      { vk:251, label:'5', cls:'m-x2',  title:'Extra Button 2 (forward)' },
      { vk:252, label:'4', cls:'m-x1',  title:'Extra Button 1 (back)' },
    ],
  },
  // dataset: load the inlined data into this module's lookups (strings/civ/card)
  setData: function(d){
    strings = d.strings || {};
    CIV = { idToCivs:(d.civ&&d.civ.idToCivs)||{}, units:new Set((d.civ&&d.civ.units)||[]) };
    cardData = d.card || null;
    chronIds = new Set((d.card&&d.card.chronicles)||[]);
    hiddenIds = new Set((d.card&&d.card.hidden)||[]);
  },
  bindings: buildEntries,        // parsed doc -> the engine's editable rec list
  forEachEntry: forEachEntry,    // iterate raw entries (used by the layout remap)
  groupOf: groupNameOf,          // display group heading for a rec
  context: recContext,           // conflict-scope code for a rec
  classify: ctxClassify,         // do two same-combo recs clash? -> tier | null
  recName: recName,              // display name for a rec
  baseName: baseName,            // display name for a command id
  ctxLabel: ctxLabel,              // human-readable label for a conflict-context code
};

})();
