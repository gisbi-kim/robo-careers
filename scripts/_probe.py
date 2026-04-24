"""Ad-hoc probe: check atlas stats for specific researcher names.

Usage: python scripts/_probe.py name1 "name 2" ...
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.io import build_author_index, load_coauthor_network, load_papers
from common.metrics import h_index, seminal_count


def compute_hub(coauthor_json, label):
    id_to_label = {n["id"]: n["label"] for n in coauthor_json["nodes"]}
    label_to_id = {v: k for k, v in id_to_label.items()}
    i = label_to_id.get(label)
    if i is None:
        return 0
    deg = 0
    for e in coauthor_json["edges"]:
        if e["source"] == i or e["target"] == i:
            deg += 1
    return deg


def fuzzy_find(author_idx, query):
    q = query.lower()
    exact = [a for a in author_idx if a.lower() == q]
    if exact:
        return exact
    starts = [a for a in author_idx if a.lower().startswith(q)]
    if starts:
        return starts
    contains = [a for a in author_idx if q in a.lower()]
    return contains


def main():
    queries = sys.argv[1:]
    if not queries:
        print("usage: python scripts/_probe.py \"Timothy Barfoot\" \"Ayoung Kim\" ...")
        sys.exit(1)

    print("loading papers...", file=sys.stderr)
    papers = load_papers()
    author_idx = build_author_index(papers)
    print(f"  {len(author_idx):,} unique authors", file=sys.stderr)
    coauth = load_coauthor_network()

    print(f"\n{'name':<32s} {'papers':>6s} {'cites':>7s} {'h':>3s} {'span':>5s} {'500+':>5s} {'hub':>5s}")
    print("-" * 75)
    for q in queries:
        matches = fuzzy_find(author_idx, q)
        if not matches:
            print(f"{q:<32s}  NOT FOUND")
            continue
        for name in matches[:5]:
            idxs = author_idx[name]
            ps = [papers[i] for i in idxs]
            years = [p["year"] for p in ps if p["year"] > 0]
            if not years:
                continue
            cites = [p["cites"] for p in ps]
            print(f"{name:<32s} {len(ps):>6d} {sum(cites):>7d} "
                  f"{h_index(cites):>3d} {max(years)-min(years)+1:>5d} "
                  f"{seminal_count(cites, 500):>5d} {compute_hub(coauth, name):>5d}  "
                  f"[{min(years)}-{max(years)}]")


if __name__ == "__main__":
    main()
