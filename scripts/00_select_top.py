"""Phase 1: pick top-K researchers by composite score + force-include a curated list.

Composite = equal-weighted z-score sum of:
    total_cites, h_index, seminal_count (>=500 cites),
    career_span (yrs), hub_degree (edges in coauthor network).

`analysis/manual_include.json` is a list of author names to force into the top list
(bypassing min-papers). Each person gets a `natural_rank` showing where they'd sit
by composite alone among the NATURAL pool (min-paper filter applied).

Z-scores are computed ONLY from the natural pool, so adding force-includes never
displaces someone who naturally belongs in the top K.

Output: analysis/top_researchers.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.io import build_author_index, load_coauthor_network, load_papers
from common.metrics import h_index, seminal_count
from common.names import slugify


def compute_hub_degree(coauthor_json: dict) -> dict[str, int]:
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


def build_stat_record(name: str, papers: list[dict], author_idx: dict,
                      hub_deg: dict) -> dict | None:
    idxs = author_idx.get(name)
    if not idxs:
        return None
    ps = [papers[i] for i in idxs]
    years = [p["year"] for p in ps if p["year"] > 0]
    if not years:
        return None
    cites = [p["cites"] for p in ps]
    return {
        "name": name,
        "slug": slugify(name),
        "papers": len(ps),
        "total_cites": sum(cites),
        "h_index": h_index(cites),
        "seminal_count": seminal_count(cites, 500),
        "career_span": max(years) - min(years) + 1,
        "first_year": min(years),
        "last_year": max(years),
        "hub_degree": hub_deg.get(name, 0),
        "force_included": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=100)
    ap.add_argument("--min-papers", type=int, default=30)
    ap.add_argument("--include-file", default="analysis/manual_include.json")
    ap.add_argument("--out", default="analysis/top_researchers.json")
    args = ap.parse_args()

    print("Loading papers...", file=sys.stderr)
    papers = load_papers()
    author_idx = build_author_index(papers)
    print(f"  {len(papers):,} papers, {len(author_idx):,} unique authors", file=sys.stderr)

    print("Loading coauthor network...", file=sys.stderr)
    coauth = load_coauthor_network()
    hub_deg = compute_hub_degree(coauth)

    # Load manual include list
    include_names = set()
    if os.path.exists(args.include_file):
        with open(args.include_file, encoding="utf-8") as f:
            include_names = set(json.load(f))

    # NATURAL pool: anyone with >= min_papers
    natural = []
    natural_names = set()
    for author, idxs in author_idx.items():
        if len(idxs) < args.min_papers:
            continue
        rec = build_stat_record(author, papers, author_idx, hub_deg)
        if rec is None:
            continue
        rec["force_included"] = author in include_names
        natural.append(rec)
        natural_names.add(author)
    print(f"  natural pool (>= {args.min_papers} papers): {len(natural):,}", file=sys.stderr)

    # BELOW-threshold force-includes
    below = []
    missing = []
    for name in include_names:
        if name in natural_names:
            continue
        rec = build_stat_record(name, papers, author_idx, hub_deg)
        if rec is None:
            missing.append(name)
            continue
        rec["force_included"] = True
        below.append(rec)
    if missing:
        print(f"  WARN — include target not in atlas: {missing}", file=sys.stderr)
    print(f"  force-include: "
          f"{sum(1 for c in natural if c['force_included'])} natural, "
          f"{len(below)} below-threshold, "
          f"{len(missing)} missing", file=sys.stderr)

    # Compute z-score basis from NATURAL pool only
    keys = ["total_cites", "h_index", "seminal_count", "career_span", "hub_degree"]
    means = {k: sum(c[k] for c in natural) / len(natural) for k in keys}
    sds = {}
    for k in keys:
        var = sum((c[k] - means[k]) ** 2 for c in natural) / max(len(natural) - 1, 1)
        sds[k] = math.sqrt(var) if var > 0 else 1.0

    # Apply z-scores to both pools using natural means/sds
    for c in natural + below:
        for k in keys:
            c[f"z_{k}"] = (c[k] - means[k]) / sds[k]
        c["composite"] = sum(c[f"z_{k}"] for k in keys)

    # Per-metric ranks within natural pool
    for k in keys:
        sorted_by_k = sorted(natural, key=lambda x: x[k], reverse=True)
        rank_map = {c["name"]: r + 1 for r, c in enumerate(sorted_by_k)}
        for c in natural:
            c[f"rank_{k}"] = rank_map[c["name"]]

    # Natural ordering within natural pool
    natural.sort(key=lambda x: x["composite"], reverse=True)
    for r, c in enumerate(natural, start=1):
        c["natural_rank"] = r

    # Top K from natural
    top_natural = natural[: args.k]
    top_names = {c["name"] for c in top_natural}

    # Appendix: force-included natural that didn't make top-K,
    # plus all below-threshold force-includes.
    appendix_in_natural = [c for c in natural
                           if c["force_included"] and c["name"] not in top_names]
    appendix_below = list(below)
    # below-threshold natural_rank is unset — they're not in the natural pool
    for c in appendix_below:
        c["natural_rank"] = None
    appendix = appendix_in_natural + appendix_below
    appendix.sort(key=lambda x: x["composite"], reverse=True)

    final = top_natural + appendix
    for r, c in enumerate(final, start=1):
        c["rank"] = r

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({
            "k": args.k,
            "natural_pool_size": len(natural),
            "below_threshold_includes": len(below),
            "n_top_natural": len(top_natural),
            "n_force_appendix": len(appendix),
            "n_total": len(final),
            "top": final,
        }, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.out}", file=sys.stderr)

    print(f"\nNatural top (last 5 of {args.k}):", file=sys.stderr)
    for c in top_natural[-5:]:
        flag = " ★" if c.get("force_included") else ""
        print(f"  #{c['rank']:3d} {c['name']:<32s} "
              f"comp={c['composite']:6.2f}  papers={c['papers']:4d} "
              f"cites={c['total_cites']:5d} h={c['h_index']:3d}{flag}", file=sys.stderr)

    if appendix:
        print(f"\nForce-included appendix:", file=sys.stderr)
        for c in appendix:
            nr = c.get("natural_rank")
            nr_str = f"{nr}" if nr is not None else "below-threshold"
            print(f"  #{c['rank']:3d} {c['name']:<32s} natural={nr_str:>17s}  "
                  f"comp={c['composite']:6.2f}  papers={c['papers']:4d} "
                  f"cites={c['total_cites']:5d} h={c['h_index']:3d}", file=sys.stderr)


if __name__ == "__main__":
    main()
