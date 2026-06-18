#!/usr/bin/env python3
"""Build the corpus Strong's occurrence index (deliverable 3B).

Walks the interlinear corpus (BOOK/CHAPTER/VERSE.json). For each word token it
extracts every LEXICAL Strong's number -- the ones wrapped in {braces} -- folds
any disambiguation suffix to the base number (H7225G -> H7225), pads to 4 digits,
and skips the non-lexical H9xxx grammatical/punctuation range.

Output: lexicon/strongs_occurrence_index.json
  { "H7225": [ {"ref","book","chapter","verse","word_index"}, ... ], ... }

Each occurrence carries word_index so the app bolds words[word_index] directly.

Because the mount is slow, processing is sliced: build partials over a file-list
slice, then merge.

  # one-time: ls the corpus into a file list (done in shell with `find`)
  python build_occurrence_index.py --filelist /tmp/otfiles.txt --start 0 --count 5000 --part parts/p0.json
  ...
  python build_occurrence_index.py --merge parts --out ../strongs_occurrence_index.json
"""
import argparse, glob, json, os, re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))   # .../lexicon/tools
LEXICON = os.path.dirname(HERE)                     # .../lexicon
REPO = os.path.dirname(LEXICON)                     # repo root

BRACED = re.compile(r"\{([^}]+)\}")
IDNUM = re.compile(r"^([GH])(\d+)([A-Za-z]*)$")


def lexical_ids(strongs_field):
    out = []
    for inner in BRACED.findall(strongs_field or ""):
        m = IDNUM.match(inner.strip())
        if not m:
            continue
        prefix, digits, _ = m.groups()
        n = int(digits)
        if prefix == "H" and 9000 <= n <= 9999:
            continue
        out.append("%s%04d" % (prefix, n))
    return out


def read_verse(path):
    try:
        return json.load(open(os.path.join(REPO, path), encoding="utf-8"))
    except Exception:
        return None


def build_slice(filelist, start, count, part_out, workers):
    paths = [l.strip() for l in open(filelist) if l.strip()]
    paths = paths[start:start + count] if count else paths[start:]
    index = defaultdict(list)
    n_files = n_occ = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for data in ex.map(read_verse, paths):
            if not data or "words" not in data:
                continue
            n_files += 1
            base = (data.get("ref"), data.get("book"), data.get("chapter"), data.get("verse"))
            for wi, w in enumerate(data.get("words", [])):
                for sid in lexical_ids(w.get("strongs", "")):
                    index[sid].append({
                        "ref": base[0], "book": base[1],
                        "chapter": base[2], "verse": base[3], "word_index": wi,
                    })
                    n_occ += 1
    os.makedirs(os.path.dirname(part_out), exist_ok=True)
    with open(part_out, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    print("slice %d..%d : files=%d occ=%d strongs=%d -> %s"
          % (start, start + len(paths), n_files, n_occ, len(index), part_out))


def merge(parts_dir, out):
    merged = defaultdict(list)
    parts = sorted(glob.glob(os.path.join(parts_dir, "*.json")))
    for p in parts:
        d = json.load(open(p, encoding="utf-8"))
        for k, v in d.items():
            merged[k].extend(v)
    # stable sort each list by book/chapter/verse/word_index for determinism
    for k in merged:
        merged[k].sort(key=lambda o: (o.get("book") or "", o.get("chapter") or "",
                                      o.get("verse") or "", o.get("word_index", 0)))
    out_obj = {k: merged[k] for k in sorted(merged)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False)
    total = sum(len(v) for v in out_obj.values())
    print("merged %d parts: distinct strongs=%d total occ=%d -> %s"
          % (len(parts), len(out_obj), total, out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filelist")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--part")
    ap.add_argument("--workers", type=int, default=64)
    ap.add_argument("--merge")
    ap.add_argument("--out", default=os.path.join(LEXICON, "strongs_occurrence_index.json"))
    args = ap.parse_args()
    if args.merge:
        merge(args.merge, args.out)
    else:
        build_slice(args.filelist, args.start, args.count, args.part, args.workers)


if __name__ == "__main__":
    main()
