#!/usr/bin/env python3
"""Convert the unabridged BDB Hebrew lexicon CSV into per-Strong's JSON files.

Decisions (confirmed with Gabe):
  * Key by BASE Strong's number, zero-padded to 4 digits (H0003.json). The BDB
    CSV carries no suffix letters; the corpus occurrence index folds suffixes
    (H7225G -> H7225) to match.
  * Merge with existing thin lexicon files, BDB wins: BDB supplies rich
    definition / references / flagged; thin fields (translit, morph, gloss) are
    kept as fallback. Uncovered Hebrew left untouched; Greek never touched.
  * Multi-number entries (e.g. "H6_H8") are written to EVERY number they cover,
    each carrying a "covers" list. A dedicated single-number entry always wins a
    collision over a multi-number one.

Raw text preserved losslessly in `definition_html`; `definition` is cleaned prose.
"""
import argparse, csv, html, json, os, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bookmap import BOOK_BY_NUM, OT_CODES

csv.field_size_limit(10 ** 9)
HERE = Path(__file__).resolve().parent
LEXICON_DIR = HERE.parent
CSV_PATH = LEXICON_DIR / "unabridged-BDB-Hebrew-lexicon.csv" / "unabridged-BDB-Hebrew-lexicon.csv"

NIQQUD = re.compile("[֑-ׇ]")
NONCONS = re.compile("[^א-ת]")
TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
RE_H1 = re.compile(r"^\s*<h1>.*?</h1>", re.DOTALL)
RE_NAV = re.compile(r'<div class="navigation">.*?</div>', re.DOTALL)
RE_REF = re.compile(r"<ref\b([^>]*)>(.*?)</ref>", re.DOTALL)
RE_ATTR = re.compile(r'(\w+)="([^"]*)"')
RE_BDBABB = re.compile(r"bdbabb\('([^']*)'\)")
RE_PLACEHOLDER = re.compile(r"<placeholder\d+\s*/?>")


def strip_tags(s):
    s = RE_PLACEHOLDER.sub(" ", s)
    s = TAG.sub(" ", s)
    s = html.unescape(s)
    return WS.sub(" ", s).strip()


def first_inner(content, tag):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), content, re.DOTALL)
    return strip_tags(m.group(1)) if m else ""


def all_inner(content, tag):
    out, seen = [], set()
    for m in re.finditer(r"<%s>(.*?)</%s>" % (tag, tag), content, re.DOTALL):
        t = strip_tags(m.group(1))
        if t and t not in seen:
            seen.add(t); out.append(t)
    return out


def parse_refs(content):
    refs, seen = [], set()
    for m in RE_REF.finditer(content):
        attrs = dict(RE_ATTR.findall(m.group(1)))
        raw = attrs.get("ref") or strip_tags(m.group(2))
        b = attrs.get("b")
        book = BOOK_BY_NUM.get(int(b)) if b and b.isdigit() else None
        def gi(k):
            v = attrs.get(k)
            return int(v) if v and v.lstrip("-").isdigit() else None
        cb, vb, ce, ve = gi("cBegin"), gi("vBegin"), gi("cEnd"), gi("vEnd")
        key = (raw, book, cb, vb, ce, ve)
        if key in seen:
            continue
        seen.add(key)
        ref = {"raw": raw, "book": book, "chapter": cb, "verse": vb}
        if ce is not None and (ce != cb or ve != vb):
            ref["chapterEnd"] = ce; ref["verseEnd"] = ve
        refs.append(ref)
    return refs


def build_body(content):
    body = RE_H1.sub("", content)
    return RE_NAV.sub("", body, count=1)


def parse_entry(content):
    body = build_body(content)
    word = first_inner(body, "bdbheb")
    word = re.sub(r"^[\[\(\s]+|[\]\)\s,;.]+$", "", word)
    return {
        "word": word,
        "pos": first_inner(body, "b"),
        "gloss": first_inner(body, "highlightword") or first_inner(body, "highlight"),
        "definition": strip_tags(body),
        "definition_html": content,
        "references": parse_refs(body),
        "flagged": {
            "hebrew": all_inner(body, "bdbheb"),
            "aramaic": all_inner(body, "bdbarc"),
            "greek": all_inner(body, "grk"),
            "translit": all_inner(body, "transliteration"),
            "abbreviations": sorted(set(RE_BDBABB.findall(body))),
        },
    }


def split_numbers(sn):
    out = []
    for part in sn.strip().split("_"):
        m = re.match(r"^H(\d+)$", part.strip())
        if m:
            n = int(m.group(1))
            if 9000 <= n <= 9999:
                continue  # H9xxx are grammatical/punctuation, never get a lexicon file
            out.append(n)
    return out


def base_filename(num):
    return "H%04d.json" % num


def root_of_header(content):
    cons = NONCONS.sub("", NIQQUD.sub("", first_inner(build_body(content), "bdbheb")))
    return cons if 2 <= len(cons) <= 4 else None


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--take", type=int, default=0)
    args = ap.parse_args()

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8"), delimiter="\t"))
    if args.limit:
        rows = rows[: args.limit]

    existing = set(os.listdir(LEXICON_DIR))
    suffix_variant = {}
    for fn in sorted(existing):
        m = re.match(r"^H(\d+)[A-Z]\.json$", fn)
        if m:
            suffix_variant.setdefault(int(m.group(1)), fn)

    current_root = None
    by_num = {}
    multi_rows = skipped_empty = 0
    collisions = Counter()
    for r in rows:
        sn = (r["StrongNumber"] or "").strip()
        nums = split_numbers(sn)
        if not nums:
            root = root_of_header(r["content"])
            if root:
                current_root = root
            skipped_empty += 1
            continue
        entry = parse_entry(r["content"])
        entry["root"] = current_root
        entry["covers"] = ["H%d" % n for n in nums] if len(nums) > 1 else []
        entry["bdbid"] = r["BDBid"]
        if len(nums) > 1:
            multi_rows += 1
        for idx, n in enumerate(nums):
            prio = (1 if len(nums) == 1 else 0, 1 if idx == 0 else 0, -len(nums))
            if n in by_num:
                collisions[n] += 1
                if prio <= by_num[n]["_prio"]:
                    continue
            by_num[n] = {**entry, "_prio": prio}

    written = merged = created = ref_total = 0
    sample = []
    nums_sorted = sorted(by_num)
    if args.skip or args.take:
        end = args.skip + args.take if args.take else len(nums_sorted)
        nums_sorted = nums_sorted[args.skip:end]
    for num in nums_sorted:
        e = by_num[num]
        fname = base_filename(num)
        path = LEXICON_DIR / fname
        thin = load_json(path) if fname in existing else None
        if thin is None and num in suffix_variant:
            thin = load_json(LEXICON_DIR / suffix_variant[num])
        t = thin or {}
        record = {
            "strongs": "H%04d" % num,
            "word": e["word"] or t.get("word", ""),
            "translit": t.get("translit", ""),
            "root": e["root"] or "",
            "morph": t.get("morph", ""),
            "pos": e["pos"],
            "gloss": e["gloss"] or t.get("gloss", ""),
            "definition": e["definition"],
            "definition_html": e["definition_html"],
            "references": e["references"],
            "flagged": e["flagged"],
            "covers": e["covers"],
            "bdbid": e["bdbid"],
            "source": "BDB",
            "testament": "OT",
        }
        ref_total += len(e["references"])
        if thin is not None:
            merged += 1
        else:
            created += 1
        if not args.dry_run:
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            written += 1
        if len(sample) < 3 and e["references"]:
            sample.append(record)

    print("=== CONVERSION REPORT ===")
    print("CSV rows processed:        %d" % len(rows))
    print("empty-SN rows skipped:     %d" % skipped_empty)
    print("multi-number rows:         %d" % multi_rows)
    print("distinct base numbers:     %d" % len(by_num))
    print("  merged into existing:    %d" % merged)
    print("  newly created:           %d" % created)
    print("base-number collisions:    %d across %d numbers" % (sum(collisions.values()), len(collisions)))
    print("total references parsed:   %d" % ref_total)
    print("(ref->corpus resolution validated by the verify step)")
    if not args.dry_run:
        print("files written:             %d" % written)
    print("\n=== SAMPLE ENTRIES ===")
    for s in sample:
        small = {k: v for k, v in s.items() if k != "definition_html"}
        small["definition"] = small["definition"][:200] + "..."
        print(json.dumps(small, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
