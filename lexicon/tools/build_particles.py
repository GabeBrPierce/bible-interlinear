#!/usr/bin/env python3
"""Build a SEPARATE particle reference for the H9xxx grammatical codes.

H9xxx codes are non-lexical (article, conjunctions, inseparable prepositions,
maqqef, sof passuq, ...) and are deliberately excluded from the per-Strong's
lexicon files and the occurrence index. This builds their own namespace so the
app can still show a particle's meaning, without polluting the lexical scheme.

Output: lexicon/particles.json  -- a single map keyed by H9xxx code:
  { "H9003": { strongs, word, translit, gloss, definition, morph, testament,
               bdb: { gloss, pos, definition, definition_html, references,
                      flagged, bdbid, shared } | null },
    ... }

The existing thin H9xxx files supply word/translit/gloss/definition for all 49
codes. BDB adds rich prose for six particle stems; BDB's single waw (vav) entry
is attached to BOTH thin vav forms (H9001 verbal, H9002 conjunctive).
"""
import csv, json, os, re, sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 9)
HERE = Path(__file__).resolve().parent
LEXICON = HERE.parent
CSV_PATH = LEXICON / "unabridged-BDB-Hebrew-lexicon.csv" / "unabridged-BDB-Hebrew-lexicon.csv"
sys.path.insert(0, str(HERE))
import convert_bdb as C   # reuse parse_entry / strip_tags

# BDB stem code -> thin code(s) it enriches
BDB_TO_THIN = {
    "H9003": ["H9003"], "H9004": ["H9004"], "H9005": ["H9005"],
    "H9008": ["H9008"], "H9009": ["H9009"],
    "H9000": ["H9001", "H9002"],   # BDB waw entry covers both vav forms
}
PARTICLE_KW = ("preposition", "conjunction", "article", "adverb",
               "interrogative", "particle", "relative", "demonstrative",
               "sign of", "mark of")


def pick_particle_row(rows):
    """From the rows for one stem, choose the particle sense (not the
    'Nth letter of the alphabet' blurb). Prefer a row matching a particle
    keyword; tie-break on length."""
    scored = []
    for content in rows:
        e = C.parse_entry(content)
        text = e["definition"].lower()
        is_alpha = bool(re.search(r"\bletter\b", text[:60]))
        kw = any(k in text for k in PARTICLE_KW)
        scored.append(((1 if kw else 0, 0 if is_alpha else 1, len(text)), e, content))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def main():
    rows_by_stem = defaultdict(list)
    for r in csv.DictReader(CSV_PATH.open(encoding="utf-8"), delimiter="\t"):
        sn = (r["StrongNumber"] or "").strip()
        if re.match(r"^H9\d{3}$", sn):
            rows_by_stem[sn].append((r["content"], r["BDBid"]))

    bdb_entry = {}
    for stem, items in rows_by_stem.items():
        e = pick_particle_row([c for c, _ in items])
        # bdbid of the chosen row
        bid = next((b for c, b in items if c == e["definition_html"]), items[0][1])
        bdb_entry[stem] = {
            "gloss": e["gloss"],
            "pos": e["pos"],
            "definition": e["definition"],
            "definition_html": e["definition_html"],
            "references": e["references"],
            "flagged": e["flagged"],
            "bdbid": bid,
        }

    particles = {}
    existing = sorted(LEXICON.glob("H9[0-9][0-9][0-9].json"))
    for path in existing:
        code = path.stem
        thin = json.loads(path.read_text(encoding="utf-8"))
        entry = {
            "strongs": code,
            "word": thin.get("word", ""),
            "translit": thin.get("translit", ""),
            "gloss": thin.get("gloss", ""),
            "definition": thin.get("definition", ""),
            "morph": thin.get("morph", ""),
            "testament": thin.get("testament", "OT"),
            "bdb": None,
        }
        for stem, targets in BDB_TO_THIN.items():
            if code in targets and stem in bdb_entry:
                b = dict(bdb_entry[stem])
                b["shared"] = len(BDB_TO_THIN[stem]) > 1
                b["bdb_stem"] = stem
                entry["bdb"] = b
        particles[code] = entry

    out = {k: particles[k] for k in sorted(particles)}
    (LEXICON / "particles.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    enriched = [k for k, v in out.items() if v["bdb"]]
    print("particles written: %d codes -> lexicon/particles.json" % len(out))
    print("BDB-enriched codes: %s" % ", ".join(enriched))
    for k in enriched:
        b = out[k]["bdb"]
        print("  %s %s  thin=%r  bdb_gloss=%r  refs=%d  shared=%s"
              % (k, out[k]["word"], out[k]["gloss"], b["gloss"], len(b["references"]), b["shared"]))


if __name__ == "__main__":
    main()
