# Handoff: BDB CSV to Per-Strong's JSON + Reference Tooling

## Your role this session

You are a senior engineering partner helping convert a Brown-Driver-Briggs (BDB)
Hebrew lexicon CSV into the data format used by the `bible-interlinear` app, and
building tooling around it. Treat this document as the source of truth for context;
ask before deviating from the schema.

Repo root: `D:\source\repos\bible-interlinear`
Stack preference: Python for scripts (CSV/JSON/regex/Unicode). Behavior-focused, not
over-engineered.

---

## The goal in one paragraph

The app has an interlinear corpus (the Hebrew/Greek text, tokenized word-by-word, each
token tagged with a Strong's number). We are adding a lexicon layer. We need one JSON
file per Strong's ID so that any interlinear word can link to its lexicon entry, and any
lexicon entry can link back out to (a) the verses it cites in its own prose and (b) every
verse in the corpus where that Strong's number actually appears, so the app can pull those
verses and highlight the specific word being discussed.

---

## Three deliverables, in priority order

1. **Per-Strong's JSON files** generated from the BDB CSV, one file per Strong's ID,
   matching the target schema below.
2. **A "flagging" script** that scans every generated entry and reports non-English
   tokens (Hebrew, Greek, transliteration) and abbreviations, so we can build a complete
   decode legend. The seed legend is below; the script's job is to surface what is missing.
3. **Verse-reference extraction**: parse Scripture citations out of each BDB entry into
   structured `{book, chapter, verse}` objects, and provide a corpus cross-reference that,
   given a Strong's number, returns every interlinear occurrence (verse ref + word index)
   for highlighting.

---

## What already exists: the interlinear corpus

Layout is `BOOK/CHAPTER/VERSE.json`, e.g. `GEN\1\1.json` through `GEN\1\31.json`.
Book codes are USFM-style 3-letter uppercase (`GEN`, `EXO`, `PSA`, `PRO`, ...).

Example, `GEN\1\1.json`:

```json
{
    "ref": "Gen.1.1",
    "book": "GEN",
    "chapter": "1",
    "verse": "1",
    "testament": "OT",
    "words": [
        {
            "original": "בְּ/רֵאשִׁ֖ית",
            "translit": "be./re.Shit",
            "strongs": "H9003/{H7225G}",
            "morph": "HR/Ncfsa",
            "gloss": "in/ beginning"
        },
        {
            "original": "בָּרָ֣א",
            "translit": "ba.Ra'",
            "strongs": "{H1254A}",
            "morph": "HVqp3ms",
            "gloss": "he created"
        }
    ]
}
```

### Strong's ID conventions in the corpus (CRITICAL for linking)

The `strongs` field on a word token is a compound string. Decode rules:

- `/` joins morphemes inside one word token (prefix + stem). `H9003/{H7225G}` is the
  preposition "be-" plus the lexical word "reshith".
- `{ }` wraps the **lexical** Strong's number (the one that has a BDB entry).
  Numbers without braces are grammatical morphemes.
- A trailing letter on a number (`H7225G`, `H1254A`, `H0430G`) is a **disambiguation
  suffix**: cases where one classic Strong's number was split into distinct words/senses.
  The base number is the digits; the suffix narrows it. Decide early whether lexicon
  files are keyed by base (`H7225`) or base+suffix (`H7225G`). Recommendation: key by the
  full ID including suffix when the BDB CSV distinguishes them, and keep a base-number
  index for fallback lookups.
- `\\` separates a word from trailing punctuation. `H9009/{H0776G}\\H9016` is "the earth"
  followed by `H9016` = sof passuq (end-of-verse mark).
- The `H9xxx` range is **not lexical**. These are added grammatical/punctuation codes
  (article, conjunction, prepositions, maqqef, sof passuq, etc.). They have no BDB entry.
  The cross-reference index must skip them.

So to find every occurrence of a lexical word: strip braces, optionally fold the suffix,
ignore `H9xxx`, and match against the BDB entry's ID.

---

## What already exists: the current lexicon entry shape

Earlier entries (from a different, thinner source and from Abbott-Smith for Greek) look
like this. The BDB output should be a superset of these fields.

Thin Hebrew example:
```json
{"strongs":"H8546","word":"תְּמוּתָה","translit":"te.mu.tah","morph":"H:N-F","gloss":"death","definition":"death","testament":"OT"}
```

Rich Greek example (note the `(AS)` = Abbott-Smith tag and heavy abbreviation use):
```json
{"strongs":"G0041","word":"ἁγιότης","translit":"hagiotēs","morph":"G:N-F","gloss":"holiness","definition":"ἁγιότης, -ητος, ἡ \n (ἅγιος), [in LXX: 2Ma.15:2 * ;] \nsanctity, holiness ... 2Co.1:12, Heb.12:10.†\n (AS)","testament":"NT"}
```

---

## Target schema for the BDB JSON files

One file per Strong's ID, filename = the ID (e.g. `H7225G.json`). Proposed fields:

```json
{
  "strongs": "H7225G",
  "word": "רֵאשִׁית",
  "translit": "re.shit",
  "root": "ראש",
  "morph": "H:N-F",
  "pos": "noun feminine",
  "gloss": "beginning",
  "definition": "<full BDB prose, cleaned>",
  "references": [
    {"raw": "Gn 1:1", "book": "GEN", "chapter": 1, "verse": 1}
  ],
  "flagged": {
    "hebrew": ["רֵאשִׁית"],
    "greek": [],
    "translit": [],
    "abbreviations": ["cf.", "v.", "Ges."]
  },
  "testament": "OT"
}
```

Notes:
- `root` matters because **BDB is organized by three-letter root**, not alphabetically.
  Capture each word's root if the CSV provides it; it powers "show related words."
- `references` is parsed from the definition prose (see parsing spec).
- `flagged` is produced by the flagging script and is for our own legend-building and QA;
  the app can ignore it or use it to render tooltips.
- Keep the raw BDB definition text intact in `definition`; do destructive cleanup only in
  derived fields.

---

## Step 0 before writing any parser: inspect the CSV

Neither of us has seen the BDB CSV. First action: load it and print the header row, the
first 5 rows, row count, and the delimiter. Report back the column names and a sample so
we can map columns to the schema. Do not assume column names. Watch for:
- Strong's number column and whether it carries suffix letters.
- Whether Hebrew is vocalized (with niqqud) or consonantal only.
- Whether transliteration, root, part of speech, and gloss are separate columns or buried
  in one definition blob.
- Encoding (must be UTF-8; Hebrew will break under cp1252).

---

## Flagging script spec (deliverable 2)

Purpose: discover, not just match. Output a per-entry report and a global tally so we can
extend the legend below until the "unknown" bucket is empty.

Algorithm:
1. For each entry, tokenize the `definition` text.
2. **Non-English detection** by Unicode block on each run of non-ASCII characters:
   - Hebrew: `U+0590`–`U+05FF`, plus presentation forms `U+FB1D`–`U+FB4F`.
   - Greek: `U+0370`–`U+03FF`, plus Greek Extended `U+1F00`–`U+1FFF`.
   - Anything else non-ASCII (combining diacritics on transliteration, etc.) -> bucket
     "translit/other".
3. **Abbreviation detection** on ASCII tokens, since Latin abbreviations are plain ASCII
   and will not trip the non-ASCII pass. Flag a token if it:
   - matches the known-abbreviation set (seed below), OR
   - is all-caps length 2 to 5 (`LXX`, `MT`, `KJV`, `DB`, `MM`, `VGT`), OR
   - ends in `.` and is length <= 5 and not a normal sentence end (`cf.`, `pl.`, `v.`,
     `q.v.`, `cstr.`, `Ges.`), OR
   - contains a symbol from the symbol set (`§ † * √ ‖ =`).
4. Emit: per entry `{strongs, hebrew[], greek[], translit[], abbreviations[]}` and a global
   `unknown_abbreviations` frequency list (anything flagged that is not yet in the legend),
   sorted by count so we triage the common ones first.

Skeleton:

```python
import csv, json, re, unicodedata
from pathlib import Path

HEBREW   = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]+')
GREEK    = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]+')
ABBREV_LIKE = re.compile(r'\b([A-Z]{2,5}|[A-Za-z]{1,4}\.)\b')
SYMBOLS  = set('§†*√‖=')

KNOWN_ABBREV = { "cf.": "compare", "LXX": "Septuagint", "MT": "Masoretic Text", ... }

def flag_entry(text):
    return {
        "hebrew": HEBREW.findall(text),
        "greek": GREEK.findall(text),
        "abbreviations": sorted(set(m.group(0) for m in ABBREV_LIKE.finditer(text))),
        "symbols": sorted(set(c for c in text if c in SYMBOLS)),
    }
```

---

## Verse-reference parsing spec (deliverable 3, part A)

Parse citations like `Gn 1:1`, `Ps 102:21`, `Ex 18:8`, `1 K 22:14`, ranges `Is 1:2-4`,
and lists `Gn 1:1; 2:4; Ps 8:2` out of the BDB prose into structured refs.

Requirements:
- Build a `BDB_BOOK_ABBREV -> USFM_CODE` map. BDB uses its own abbreviations (`Gn`, `Ex`,
  `Lv`, `Nu`, `Dt`, `Jos`, `Ju`, `Ps`, `Pr`, `Jb`, `Is`, `Je`, `Ez`, `Dn`, ...), which
  differ from the corpus codes (`GEN`, `EXO`, `PSA`, ...). The flagging script will surface
  the actual abbreviations the CSV uses; build the map from that, do not guess blindly.
- Handle list continuation: after `Ps 102:21; 79:11`, the second item inherits book `Ps`.
- Handle ranges and comma-separated verses.
- **Versification caveat**: BDB uses Hebrew (BHS) versification. The interlinear is the
  Hebrew text, so they should align, but Psalms and a few books differ from English Bibles
  (e.g. Hebrew Ps 102:21 = English 102:20, superscriptions shift verse numbers). Keep
  everything in Hebrew versification to match the corpus. Flag any reference that fails to
  resolve against an existing corpus file so we can catch versification mismatches.
- Store both `raw` (original string) and the parsed fields, so nothing is lost if a parse
  is wrong.

---

## Corpus cross-reference + highlighting (deliverable 3, part B)

This is what makes "pull the verses and highlight the word" work.

Build an index over the whole `BOOK/CHAPTER/VERSE.json` corpus:
- For each verse file, for each word token, extract every lexical Strong's number
  (strip `{}`, fold or keep suffix per our decision, skip `H9xxx`).
- Map `strongs_id -> [ {ref, book, chapter, verse, word_index} ]`.

Then:
- **Entry to verses**: a lexicon entry for `H7225G` looks itself up in the index to get all
  occurrences. Combined with the parsed `references`, the app can show "cited here" and
  "appears here" lists.
- **Highlighting**: each occurrence carries `word_index`, so the app renders the verse from
  the interlinear and bolds `words[word_index]`. No fuzzy text matching needed; the index
  is the source of truth.

Persist this index as a separate artifact (e.g. `strongs_occurrence_index.json`) rather
than stuffing occurrences into every lexicon file, so the lexicon files stay small and the
index can be regenerated when the corpus changes.

---

## Seed decode legend (extend via the flagging script)

This is a starting set, drawn from the Greek (Abbott-Smith) and Hebrew sources seen so
far. BDB leans heavily on comparative-language and grammatical abbreviations, so expect the
script to add many more. The script's `unknown_abbreviations` output drives expansion.

**Symbols**
- `†` all NT occurrences of the word are cited (Abbott-Smith)
- `*` all LXX occurrences are cited
- `§` section (e.g. Trench section, Roman numerals)
- `√` root (BDB)
- `‖` parallel passage
- `=` equivalent to

**General**
- `cf.` compare | `LXX` Septuagint | `MT` Masoretic Text | `Heb.` Hebrew
- `v.` / `vid.` see | `q.v.` which see | `id.` the same | `om.` omit | `rd.` read
- `opp.` opposite | `esp.` especially | `prob.` probably | `fig.` figurative
- `metaph.` metaphorically | `indecl.` indeclinable | `pl.` plural | `du.` dual
- `Qere` word as read | `Ketiv` word as written | `KJV` King James Version

**Grammar (BDB-style)**
- `abs.` absolute | `cstr.` construct | `sf.` suffix | `coll.` collective
- `n.m.` noun masculine | `n.f.` noun feminine | `adj.` adjective | `vb.` verb
- `pt.` / `ptcp.` participle | `pf.` perfect | `impf.` imperfect | `inf.` infinitive

**Comparative languages (BDB)**
- `Ar.` Arabic | `Aram.` Aramaic | `BAram.` Biblical Aramaic | `As.`/`Assyr.` Assyrian
- `Eth.` Ethiopic | `Ph.` Phoenician | `Sab.` Sabean | `Syr.` Syriac | `NH` New Hebrew

**Cited works / scholars (sample, expect many)**
- `Ges.` Gesenius | `Thes.` Gesenius Thesaurus | `Dr.` Driver | `We.` Wellhausen
- `AS` Abbott-Smith | `MM, VGT` Moulton-Milligan Vocabulary of the Greek Testament
- `Tr., Syn.` Trench Synonyms | `Cremer` Cremer lexicon | `DB` Hastings Dictionary of the Bible

**Book abbreviations**: build from the CSV. Map every BDB form to the corpus USFM code.

---

## Edge cases / gotchas

- UTF-8 everywhere. Verify Hebrew round-trips before bulk processing.
- Suffix-letter decision (base vs base+suffix keying) is foundational; decide it first and
  apply consistently to filenames, the cross-reference index, and lookups.
- `H9xxx` codes must never get a lexicon file and must be excluded from occurrence counts.
- BDB entries can cover several related words under one root; confirm whether the CSV is one
  row per Strong's ID or one row per root with multiple IDs inside.
- Keep raw text intact; all cleanup goes into derived fields only.
- Validate parsed references against existing corpus files and report unresolved ones.

---

## Suggested order of work

1. Inspect the CSV, report columns and a sample. Wait for schema confirmation.
2. Write the converter producing per-Strong's JSON files (raw definition + basic fields).
3. Run the flagging script; expand the legend until unknowns are triaged.
4. Add reference parsing using the discovered book abbreviations.
5. Build the corpus occurrence index and wire up highlighting.

## Open questions to confirm with Gabe

- Output directory for the lexicon JSON files?
- Key files by base Strong's number or base+suffix?
- One CSV row per Strong's ID, or per root?
- Should Greek (Abbott-Smith) entries be reprocessed the same way later, or is this
  session Hebrew/BDB only?

---

## Session 2 — completed (2026-06-18)

Decisions locked with Gabe: key by **base** Strong's number (4-digit pad,
`H0003.json`); **merge into `lexicon/` root, BDB wins** (thin translit/morph/gloss
kept as fallback, uncovered Hebrew + all Greek untouched); multi-number rows
written to **every** number they cover (`covers` field); H9xxx never get a file.

What the CSV turned out to be: tab-delimited, 3 cols (`BDBid`, `StrongNumber`,
`content`), UTF-8, 10,022 rows. `content` is richly tagged HTML — verse refs are
fully structured `<ref b=.. cBegin=.. vBegin=..>` (no prose parsing needed),
abbreviations tagged via `<lookup onclick="bdbabb('..')">`, Hebrew `<bdbheb>`,
Aramaic `<bdbarc>`, Greek `<grk>`, translit `<transliteration>`, gloss
`<highlightword>`. `b` is the standard 1-66 canonical book number.

Deliverables (all in `lexicon/tools/`):
  * `bookmap.py` — b-number -> USFM code map (+ OT_CODES).
  * `convert_bdb.py` — CSV -> per-base-number JSON, merged with thin files.
    Schema adds: `root`, `pos`, `definition_html` (lossless raw), `references`,
    `flagged` (hebrew/aramaic/greek/translit/abbreviations), `covers`, `bdbid`,
    `source:"BDB"`. Sliced (`--skip/--take`) because the mount is slow.
  * `flag_legend.py` -> `flagging_report.json` + `decode_legend.md`
    (335 distinct sigla; 334 need expansion — triage table sorted by frequency).
  * `build_occurrence_index.py` -> `../strongs_occurrence_index.json`
    (folds suffix H7225G->H7225, skips H9xxx). Sliced + `--merge`.

Results: 8,619 base lexicon files written (8,617 merged, 2 net-new base names;
~1,389 base files materialised where only suffixed thin files existed before —
suffixed thin files left in place). 136,633 references parsed. Occurrence index:
23,261 OT verses, 8,513 distinct Strong's, 299,594 lexical occurrences.

Verification: schema 249/249 sample complete + UTF-8 clean; 98.5% of OT refs
resolve to corpus files (remaining ~1.5% are Hebrew-vs-English versification, as
anticipated — a full unresolved-ref report is not yet generated); end-to-end
highlight (index word_index -> token strongs) 5/5. The 6 H9xxx rows BDB actually
carries (letter-particles) were excluded; 5 pre-existing thin H9xxx files
restored from git, 1 net-new deleted.

Backup: pre-run tree is clean in git (`git restore lexicon/` reverts everything).

Open / next session:
  * A few multi-number combined entries pick an odd headword `word` (e.g.
    `H0004` shows a siglum); gloss/refs/raw are fine. Could refine lemma pick.
  * Expand `decode_legend.md` meanings (BDB abbreviations table not in CSV).
  * Optionally generate a full unresolved-reference report for versification QA.
  * Greek/Abbott-Smith reprocessing deferred (this session was Hebrew/BDB only).

### Particle reference (added)

H9xxx particles kept in their own namespace (not lexical, not in the occurrence
index). `lexicon/tools/build_particles.py` -> `lexicon/particles.json`: a single
map of all 49 H9xxx codes (thin word/translit/gloss/definition for each), with
BDB rich prose attached to the 6 stems BDB describes — be- (H9003), ke- (H9004),
le- (H9005), interrogative he (H9008), article he (H9009), and the waw entry
(BDB H9000) attached to both vav forms (H9001, H9002) as a shared entry. Marks
like maqqef (H9014) and sof passuq (H9016) carry `bdb: null`.
