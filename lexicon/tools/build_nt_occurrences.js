/**
 * build_nt_occurrences.js
 * Builds Greek (NT) occurrence files by scanning the interlinear verse data in
 * the repo (BOOK/<chapter>/<verse>.json). For every Greek word it records the
 * verse, then writes one compact file per Strong's number to lexicon/occ/<KEY>.json
 * — the same format and location as the Hebrew split (see split_occurrences.js),
 * so the app fetches NT and OT references identically.
 *
 * Each output file is an array of [bookCode, chapter, verse] tuples.
 *
 * Usage:  node lexicon/tools/build_nt_occurrences.js
 */

const fs   = require('fs');
const path = require('path');

const REPO    = path.resolve(__dirname, '..', '..');       // …/bible-interlinear
const OUT     = path.join(REPO, 'lexicon', 'occ');

const NT_BOOKS = [
  'MAT','MRK','LUK','JHN','ACT','ROM','1CO','2CO','GAL','EPH','PHP','COL',
  '1TH','2TH','1TI','2TI','TIT','PHM','HEB','JAS','1PE','2PE','1JN','2JN','3JN','JUD','REV',
];

// Mirror of strongsToLexKey in the app: resolve a token's compound `strongs`
// field to its lexicon key (e.g. "G0025"). NT tokens are simple ("G3779").
function toKey(strongsField) {
  if (!strongsField) return null;
  const raw = Array.isArray(strongsField) ? strongsField.join('/') : String(strongsField);
  let id = null;
  const braced = raw.match(/\{([^}]+)\}/g);
  if (braced && braced.length) {
    id = braced[0].replace(/[{}]/g, '');
  } else {
    const ids = raw.match(/[GH]\d+[A-Za-z]?/g) || [];
    id = ids.find((t) => !/^H9\d{3}$/.test(t)) || ids[0] || null;
  }
  if (!id) return null;
  const m = id.match(/^([GH])(\d+)([A-Za-z]*)$/);
  if (!m) return null;
  return m[1] + String(parseInt(m[2], 10)).padStart(4, '0');
}

fs.mkdirSync(OUT, { recursive: true });

const index = {}; // key -> [[book, chapter, verse], …]
let verseFiles = 0;

for (const book of NT_BOOKS) {
  const bookDir = path.join(REPO, book);
  if (!fs.existsSync(bookDir)) { console.warn(`(skip, missing) ${book}`); continue; }
  for (const ch of fs.readdirSync(bookDir)) {
    const chDir = path.join(bookDir, ch);
    if (!fs.statSync(chDir).isDirectory()) continue;
    for (const vf of fs.readdirSync(chDir)) {
      if (!vf.endsWith('.json')) continue;
      let data;
      try { data = JSON.parse(fs.readFileSync(path.join(chDir, vf), 'utf8')); }
      catch (_) { continue; }
      verseFiles++;
      const chapter = parseInt(data.chapter, 10);
      const verse   = parseInt(data.verse, 10);
      for (const w of (data.words || [])) {
        const key = toKey(w.strongs);
        if (!key || key[0] !== 'G') continue; // Greek only
        (index[key] || (index[key] = [])).push([book, chapter, verse]);
      }
    }
  }
}

let files = 0, occs = 0;
for (const key of Object.keys(index)) {
  occs += index[key].length;
  fs.writeFileSync(path.join(OUT, `${key}.json`), JSON.stringify(index[key]));
  files++;
}

console.log(`Scanned ${verseFiles} NT verse files.`);
console.log(`Wrote ${files} Greek occurrence files (${occs} occurrences) to lexicon/occ/`);
