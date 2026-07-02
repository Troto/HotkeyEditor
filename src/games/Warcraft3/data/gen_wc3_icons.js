#!/usr/bin/env node
/*
 * gen_wc3_icons.js -- (re)build wc3_icons.json + vendor the classic ability icons from the
 * upstream jcfieldsdev/warcraft3-hotkey-editor editor (MIT -- see SOURCE.md).
 *
 * The upstream `data.js` carries a `data.icons` map we deliberately did NOT copy when we first
 * imported the data (gen_wc3_data.js drops it).  This one-off script extracts the *classic* set
 * -- `data.icons.classic.commands` = { 4-char command code -> icon basename } -- writes it to
 * wc3_icons.json, and downloads every referenced `<basename>.png` into data/icons/classic/ so the
 * build can copy them next to the page (see game_module_generator.py).  The editor shows an icon
 * on a keyboard key when you select a command card; the map turns a binding's code into its icon.
 *
 * Usage:
 *   node gen_wc3_icons.js <path-to-upstream/data.js> [--download]
 *     (no --download: just rewrite wc3_icons.json from the local data.js copy)
 *
 * Only the classic set is vendored for now (it maps every carded command; the reforged set is
 * partial upstream).  Requires Node 18+ for global fetch when --download is passed.
 */
'use strict';
const fs = require('fs');
const path = require('path');

const HERE = __dirname;                                   // games/Warcraft3/data
const RAW_BASE = 'https://raw.githubusercontent.com/jcfieldsdev/warcraft3-hotkey-editor/master/www/icons/classic';

function sliceObject(src, marker) {                       // brace-match the object literal after `marker`
  const start = src.indexOf(marker);
  if (start < 0) throw new Error('marker not found: ' + marker);
  const from = src.indexOf('{', start);
  let depth = 0, i = from;
  for (; i < src.length; i++) {
    const c = src[i];
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (!depth) { i++; break; } }
  }
  return src.slice(from, i);
}

async function main() {
  const dataJsPath = process.argv[2];
  const download = process.argv.includes('--download');
  if (!dataJsPath) {
    console.error('usage: node gen_wc3_icons.js <path-to-data.js> [--download]');
    process.exit(1);
  }
  const src = fs.readFileSync(dataJsPath, 'utf8');
  const icons = eval('(' + sliceObject(src, 'data.icons =') + ')');   // { classic:{extension,commands}, reforged:{...} }
  const commands = icons.classic.commands;                            // code -> basename

  const sorted = {};                                                  // stable, diff-friendly ordering
  Object.keys(commands).sort().forEach(function (k) { sorted[k] = commands[k]; });
  const outPath = path.join(HERE, 'wc3_icons.json');
  fs.writeFileSync(outPath, JSON.stringify({ classic: sorted }, null, 0) + '\n');
  const files = [...new Set(Object.values(commands))].sort();
  console.log('wrote ' + path.relative(process.cwd(), outPath) +
    ' (' + Object.keys(commands).length + ' codes, ' + files.length + ' unique icons)');

  if (!download) { console.log('(pass --download to also fetch the PNGs)'); return; }
  const destDir = path.join(HERE, 'icons', 'classic');
  fs.mkdirSync(destDir, { recursive: true });
  let done = 0, failed = 0;
  const queue = files.slice();
  async function worker() {
    for (;;) {
      const name = queue.shift();
      if (!name) return;
      const dest = path.join(destDir, name + '.png');
      try {
        const res = await fetch(RAW_BASE + '/' + name + '.png');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        fs.writeFileSync(dest, Buffer.from(await res.arrayBuffer()));
        done++;
      } catch (e) { failed++; console.error('FAIL ' + name + ': ' + e.message); }
    }
  }
  await Promise.all(Array.from({ length: 16 }, worker));             // 16 parallel fetches
  console.log('downloaded ' + done + ' icons to ' + path.relative(process.cwd(), destDir) +
    (failed ? ' (' + failed + ' failed)' : ''));
}

main().catch(function (e) { console.error(e); process.exit(1); });
