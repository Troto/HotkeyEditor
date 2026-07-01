#!/usr/bin/env node
// One-off converter: upstream data.js + index.html (jcfieldsdev/warcraft3-hotkey-editor, MIT)
// -> wc3.json.  See SOURCE.md for provenance/attribution.
//   Usage:  node gen_wc3_data.js path/to/data.js path/to/index.html
// Evaluates data.js in a function scope, keeps {units, common, buildCommands, campaignRaces}
// (drops the icon map), maps the numeric `type` enum to short strings, and adds `shown` -- the
// curated list of browsable unit codes (the `<a href="#code">` links in index.html), which is
// the editor's filter for actually-playable units (data.units also holds campaign/boss units
// only needed for hotkey resolution).  Writes wc3.json.
"use strict";
const fs = require("fs");
const path = require("path");

const srcPath = process.argv[2], indexPath = process.argv[3];
if (!srcPath || !indexPath) { console.error("usage: node gen_wc3_data.js path/to/data.js path/to/index.html"); process.exit(1); }
const src = fs.readFileSync(srcPath, "utf8");

const grab = new Function(src + "\nreturn {data, OTHER,UNIT,HERO,NO_ATTACK,SUMMON,BUILDING,TOWER,ITEM};");
const X = grab();
const TYPE = { [X.OTHER]:"other", [X.UNIT]:"unit", [X.HERO]:"hero", [X.NO_ATTACK]:"noAttack",
               [X.SUMMON]:"summon", [X.BUILDING]:"building", [X.TOWER]:"tower", [X.ITEM]:"item" };

const units = {};
for (const [code, u] of Object.entries(X.data.units)) {
  units[code] = { name: u.name, race: u.race, type: TYPE[u.type], commands: u.commands || [] };
  if (u.build) units[code].build = u.build;
}
// Walk index.html tracking the race <h2> and the <h3> subsection (Melee / Campaign /
// Neutral Passive|Hostile).  `shown` = every browsable unit code (anchor target); `campaign` =
// those listed under a "Campaign" subsection (units that only appear in campaign, not melee).
const shownSet = new Set(), campaignSet = new Set();
let h3 = "";
for (const line of fs.readFileSync(indexPath, "utf8").split("\n")) {
  const h = /<h3>(.*?)<\/h3>/.exec(line);
  if (h) { h3 = h[1]; continue; }
  for (const a of line.matchAll(/href="#([A-Za-z0-9_]+)"/g)) {
    const code = a[1];
    if (!units[code]) continue;
    shownSet.add(code);
    if (/^campaign/i.test(h3)) campaignSet.add(code);
  }
}
const shown = Array.from(shownSet).sort();
const campaign = Array.from(campaignSet).sort();

const out = { units, common: X.data.common, buildCommands: X.data.buildCommands,
              campaignRaces: X.data.campaignRaces, shown: shown, campaign: campaign };

const dst = path.join(__dirname, "wc3.json");
fs.writeFileSync(dst, JSON.stringify(out));
console.log("wrote " + dst + " (" + Object.keys(units).length + " units, " + fs.statSync(dst).size + " bytes)");
