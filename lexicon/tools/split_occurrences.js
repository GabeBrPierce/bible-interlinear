/**
 * split_occurrences.js
 * Splits the monolithic strongs_occurrence_index.json into one compact file per
 * Strong's number under lexicon/occ/<KEY>.json. These are served via GitHub Pages
 * (alongside the lexicon entry files) and fetched on demand by the app, so only
 * the verses for the word being viewed are ever loaded.
 *
 * Each output file is an array of [bookCode, chapter, verse] tuples, e.g.
 *   [["1CH",12,17],["1CH",12,28], ...]
 *
 * Usage (from repo root or anywhere):  node lexicon/tools/split_occurrences.js
 */

const fs   = require('fs');
const path = require('path');

const LEXICON = path.resolve(__dirname, '..');            // …/bible-interlinear/lexicon
const SRC     = path.join(LEXICON, 'strongs_occurrence_index.json');
const OUT     = path.join(LEXICON, 'occ');

if (!fs.existsSync(SRC)) {
  console.error(`Source not found: ${SRC}`);
  process.exit(1);
}

fs.mkdirSync(OUT, { recursive: true });

// Clear any previous split so removed keys don't linger.
for (const f of fs.readdirSync(OUT)) {
  if (f.endsWith('.json')) fs.unlinkSync(path.join(OUT, f));
}

const index = JSON.parse(fs.readFileSync(SRC, 'utf8'));

let files = 0;
let occs  = 0;
for (const key of Object.keys(index)) {
  const tuples = index[key].map((o) => [
    o.book,
    parseInt(o.chapter, 10),
    parseInt(o.verse, 10),
  ]);
  occs += tuples.length;
  fs.writeFileSync(path.join(OUT, `${key}.json`), JSON.stringify(tuples));
  files++;
}

console.log(`Wrote ${files} occurrence files (${occs} occurrences) to lexicon/occ/`);
