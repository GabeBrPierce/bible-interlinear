#!/usr/bin/env python3
"""Flagging / legend-building script (deliverable 2).

Scans the BDB source for non-English tokens (Hebrew / Aramaic / Greek /
transliteration) and abbreviation sigla, then reports a global tally and the set
of abbreviations NOT yet in our decode legend, sorted by frequency so the common
ones get triaged first. Per-entry flagged data already lives in each H*.json
(written by convert_bdb.py); this produces the GLOBAL view + the legend file.

Abbreviation sigla are read straight from the tagged <lookup onclick="bdbabb('X')">
markers, so this discovers exactly what BDB actually uses rather than guessing.

Outputs:
  flagging_report.json   global tallies + unknown_abbreviations (sorted)
  decode_legend.md       seed legend + a triage table of unknown sigla
"""
import csv, json, re, sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10 ** 9)
HERE = Path(__file__).resolve().parent
LEXICON_DIR = HERE.parent
CSV_PATH = LEXICON_DIR / "unabridged-BDB-Hebrew-lexicon.csv" / "unabridged-BDB-Hebrew-lexicon.csv"

RE_BDBABB = re.compile(r"bdbabb\('([^']*)'\)")
RE_TAG = re.compile(r"<[^>]+>")
HEBREW = re.compile(r"[֐-׿יִ-ﭏ]+")
GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]+")
SYMBOLS = set("§†*√‖=")

# Seed legend from the handoff (codes/abbreviations we already understand).
KNOWN = {
    "cf.", "LXX", "MT", "Heb.", "v.", "vid.", "q.v.", "id.", "om.", "rd.",
    "opp.", "esp.", "prob.", "fig.", "metaph.", "indecl.", "pl.", "du.",
    "Qere", "Ketiv", "KJV", "abs.", "cstr.", "sf.", "coll.", "n.m.", "n.f.",
    "adj.", "vb.", "pt.", "ptcp.", "pf.", "impf.", "inf.",
    "Ar.", "Aram.", "BAram.", "As.", "Assyr.", "Eth.", "Ph.", "Sab.", "Syr.",
    "NH", "Ges.", "Thes.", "Dr.", "We.", "AS", "MM", "VGT", "Tr.", "Syn.",
    "Cremer", "DB",
}


def main():
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8"), delimiter="\t"))
    abbr = Counter()
    symbols = Counter()
    n_entries = 0
    with_heb = with_grk = with_arc = with_translit = 0
    for r in rows:
        if not (r["StrongNumber"] or "").strip():
            continue
        n_entries += 1
        c = r["content"]
        for code in RE_BDBABB.findall(c):
            abbr[code] += 1
        if "<bdbheb>" in c:
            with_heb += 1
        if "<bdbarc>" in c:
            with_arc += 1
        if "<grk>" in c:
            with_grk += 1
        if "<transliteration>" in c:
            with_translit += 1
        for ch in RE_TAG.sub(' ', c):  # visible text only, not markup
            if ch in SYMBOLS:
                symbols[ch] += 1

    unknown = Counter({k: v for k, v in abbr.items() if k not in KNOWN})
    report = {
        "source_rows": len(rows),
        "entries_with_strongs": n_entries,
        "entries_with_hebrew": with_heb,
        "entries_with_aramaic": with_arc,
        "entries_with_greek": with_grk,
        "entries_with_translit": with_translit,
        "distinct_abbreviations": len(abbr),
        "known_abbreviations": len(set(abbr) & KNOWN),
        "unknown_abbreviations_count": len(unknown),
        "abbreviation_counts": dict(abbr.most_common()),
        "unknown_abbreviations": dict(unknown.most_common()),
        "symbol_counts": dict(symbols.most_common()),
    }
    (HERE / "flagging_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# BDB decode legend (auto-generated)\n",
             "Seed legend is in the handoff. Below: every abbreviation siglum BDB",
             "actually uses, by frequency. Codes already in the seed legend are marked",
             "KNOWN; the rest need an expansion. Fill in the 'meaning' column as triaged.\n",
             "| siglum | count | status | meaning |",
             "| --- | ---: | --- | --- |"]
    for code, cnt in abbr.most_common():
        status = "KNOWN" if code in KNOWN else ""
        lines.append("| `%s` | %d | %s | |" % (code, cnt, status))
    (HERE / "decode_legend.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== FLAGGING REPORT ===")
    for k in ("source_rows", "entries_with_strongs", "entries_with_hebrew",
              "entries_with_aramaic", "entries_with_greek", "entries_with_translit",
              "distinct_abbreviations", "known_abbreviations", "unknown_abbreviations_count"):
        print("%-32s %s" % (k, report[k]))
    print("symbols:", report["symbol_counts"])
    print("top 25 abbreviations:")
    for code, cnt in abbr.most_common(25):
        print("   %-10s %5d %s" % (code, cnt, "(known)" if code in KNOWN else ""))


if __name__ == "__main__":
    main()
