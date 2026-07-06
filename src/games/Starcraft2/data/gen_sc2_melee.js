// Extracts the melee (ladder) unit/command roster from jcfieldsdev's StarCraft II hotkey editor
// dataset -- https://github.com/jcfieldsdev/starcraft2-hotkey-editor (MIT).  The extracted game
// files include co-op commanders, campaign heroes and engine-only SC1 remakes (Defiler, ...) that
// aren't playable in normal matches; jcfieldsdev's curated data marks the true melee roster by
// `commander` (the base races Terran/Protoss/Zerg).  We keep the set of melee command output-names
// so the SC2 module can filter its game-derived data down to ladder units.  See data/SOURCE.md.
//
// Usage: node gen_sc2_melee.js path/to/jcfieldsdev/data.js   ->  writes sc2_melee.json
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8');
const box = {}; vm.createContext(box); vm.runInContext(src + '\n;globalThis.__d=data;', box);
const U = (box.__d || box.data).units;
const MELEE = new Set(['Terran', 'Protoss', 'Zerg']);   // base-race commanders = ladder
const COMMANDER = 1;
const UNIT = 2, HERO = 3, BUILDING = 4;
const KIND = {}; KIND[UNIT] = 'unit'; KIND[HERO] = 'unit'; KIND[BUILDING] = 'building';
const commands = new Set(), qualifiers = new Set(), names = new Set();
const types = {};   // unit display-name AND caster id -> 'unit' | 'building'
let unitCount = 0;
for (const k in U) {
  const u = U[k];
  if (!MELEE.has(u.commander) || u.type === COMMANDER) continue;
  unitCount++;
  var kind = KIND[u.type] || 'unit';
  if (u.name) { names.add(u.name); types[u.name] = kind; }
  const c = u.commands;
  const list = Array.isArray(c) ? c : (c ? [].concat(...Object.values(c)) : []);
  list.forEach(cmd => {
    commands.add(cmd);
    const slash = cmd.lastIndexOf('/');       // "Command/Unit" -> unit is a melee caster id
    if (slash >= 0) { var q = cmd.slice(slash + 1); qualifiers.add(q); if (!(q in types)) types[q] = kind; }
  });
}
fs.writeFileSync('sc2_melee.json', JSON.stringify({
  commands: [...commands].sort(),
  qualifiers: [...qualifiers].sort(),   // SC2 unit ids that host a melee command (incl. tech labs)
  unitNames: [...names].sort(),         // display names of melee units (for ability-less units)
  types: types,                         // name/id -> 'unit' | 'building' (for column categories)
  unitCount: unitCount
}, null, 1));
console.log('melee: %d commands, %d qualifiers, %d names, %d units -> sc2_melee.json',
  commands.size, qualifiers.size, names.size, unitCount);
