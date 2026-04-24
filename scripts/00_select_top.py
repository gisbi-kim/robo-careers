"""Phase 1: pick top-K researchers by composite score.

Composite = equal-weighted z-score sum of:
    total_cites, h_index, seminal_count (>=500 cites),
    career_span (yrs), hub_degree (edges in coauthor network).

Output: analysis/top_researchers.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.io import build_author_index, load_coauthor_network, load_papers
from common.metrics import h_index, seminal_count, z_scores
from common.names import slugify


def compute_hub_degree(coauthor_json: dict) -> dict[str, int]:
    """Return label -> degree (edge count in coauthor network)."""
    id_to_label = {n["id"]: n["label"] for n in coauthor_json["nodes"]}
    deg: dict[int, int] = {}
    for e in coauthor_json["edges"]:
        a = e.get("source", e.get("s"))
        b = e.get("target", e.get("t"))
        if a is None or b is None:
            continue
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    return {id_to_label[i]: d for i, d in deg.items() if i in id_to_label}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--min-papers", type=int, default=30,
                    help="exclude authors below this paper count")
    ap.add_argument("--out", default="analysis/top_researchers.json")
    args = ap.parse_args()

    print("Loading papers...", file=sys.stderr)
    papers = load_papers()
    author_idx = build_author_index(papers)
    print(f"  {len(papers):,} papers, {len(author_idx):,} unique authors",
          file=sys.stderr)

    print("Loading coauthor network...", file=sys.stderr)
    coauth = load_coauthor_network()
    hub_deg = compute_hub_degree(coauth)

    # Build per-author stats over candidate pool
    candidates = []
    for author, idxs in author_idx.items():
        if len(idxs) < args.min_papers:
            continue
        ps = [papers[i] for i in idxs]
        years = [p["year"] for p in ps if p["year"] > 0]
        if not years:
            continue
        cites = [p["cites"] for p in ps]
        candidates.append({
            "name": author,
            "slug": slugify(author),
            "papers": len(ps),
            "total_cites": sum(cites),
            "h_index": h_index(cites),
            "seminal_count": seminal_count(cites, 500),
            "career_span": max(years) - min(years) + 1,
            "first_year": min(years),
            "last_year": max(years),
            "hub_degree": hub_deg.get(author, 0),
        })
    print(f"  candidate pool: {len(candidates):,}", file=sys.stderr)

    # Composite score
    keys = ["total_cites", "h_index", "seminal_count", "career_span", "hub_degree"]
    vectors = {k: z_scores([c[k] for c in candidates]) for k in keys}
    for i, c in enumerate(candidates):
        c["composite"] = sum(vectors[k][i] for k in keys)
        for k in keys:
            c[f"z_{k}"] = vectors[k][i]

    candidates.sort(key=lambda x: x["composite"], reverse=True)

    # Individual rank per metric (across full candidate pool)
    for k in keys:
        sorted_by_k = sorted(candidates, key=lambda x: x[k], reverse=True)
        rank_map = {c["name"]: r + 1 for r, c in enumerate(sorted_by_k)}
        for c in candidates:
            c[f"rank_{k}"] = rank_map[c["name"]]

    top = candidates[: args.k]
    for r, c in enumerate(top, start=1):
        c["rank"] = r

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({
            "k": args.k,
            "pool_size": len(candidates),
            "top": top,
        }, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.out}", file=sys.stderr)
    print("\nTop {}:".format(args.k), file=sys.stderr)
    for c in top:
        print(f"  {c['rank']:2d}. {c['name']:<32s} "
              f"papers={c['papers']:4d}  cites={c['total_cites']:6d}  "
              f"h={c['h_index']:3d}  span={c['career_span']:2d}  "
              f"hub={c['hub_degree']:3d}", file=sys.stderr)


if __name__ == "__main__":
    main()
