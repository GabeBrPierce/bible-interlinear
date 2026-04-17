# Interlinear Bible Data

Word-by-word original-language data for the 66-book Protestant Bible, parsed from the STEPBible Translators Amalgamated tagged texts.

## Attribution

This data is derived from:

- **TAGNT** — Translators Amalgamated Greek New Testament
- **TAHOT** — Translators Amalgamated Hebrew Old Testament

Created by [www.STEPBible.org](https://www.STEPBible.org) based on work at **Tyndale House, Cambridge**.

Licensed under **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**.

Source repository: [github.com/STEPBible/STEPBible-Data](https://github.com/STEPBible/STEPBible-Data)

## File structure

```
interlinear/
  index.json                 # Book list with chapter counts
  {BOOK}/{chapter}/{verse}.json
```

Examples:
- `interlinear/GEN/1/1.json` — Genesis 1:1 (Hebrew)
- `interlinear/JHN/3/16.json` — John 3:16 (Greek)
- `interlinear/PSA/23/1.json` — Psalm 23:1 (Hebrew)

Book IDs use uppercase USFM codes matching the Agape Bible app (GEN, EXO, MAT, MRK, JHN, etc.).

## Verse JSON shape

```json
{
  "ref": "Jhn.3.16",
  "book": "JHN",
  "chapter": "3",
  "verse": "16",
  "testament": "NT",
  "words": [
    {
      "original": "οὕτως",
      "translit": "houtōs",
      "strongs": "G3779",
      "morph": "ADV",
      "gloss": "Thus"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `ref` | Original STEPBible reference (mixed-case book abbreviation) |
| `book` | USFM book ID (uppercase, matches app) |
| `chapter` / `verse` | Chapter and verse numbers (strings) |
| `testament` | `"OT"` or `"NT"` |
| `words[]` | Ordered word-by-word data for the verse |
| `words[].original` | Original language text (Hebrew or Greek) |
| `words[].translit` | Transliteration into Latin script |
| `words[].strongs` | Strong's number(s), may be compound (e.g. `H9002/{H7225G}`) |
| `words[].morph` | Morphology code |
| `words[].gloss` | English translation/gloss |

## Fetch URL pattern

If hosted on GitHub Pages at `https://{user}.github.io/{repo}/`:

```
https://{user}.github.io/{repo}/interlinear/{BOOK}/{chapter}/{verse}.json
```

For local Vite dev server:

```
http://localhost:5173/interlinear/{BOOK}/{chapter}/{verse}.json
```

## Stats

- 66 books (39 OT + 27 NT)
- 31,219 verses
- 447,748 words

## Regenerating

```bash
node tools/parse-interlinear.js
```

Requires the STEPBible-Data repository at `D:/Users/gabeb/source/repos/bible-data/STEPBible-Data-master`. Override with `--data-dir <path>`. Output directory defaults to `agape-bible/public/interlinear`, override with `--out-dir <path>`.
