"""Phase 2: per-researcher profile extraction.

Usage:
    python scripts/01_extract_profile.py                  # all from top_researchers.json
    python scripts/01_extract_profile.py "Vijay Kumar"    # one researcher

Output: analysis/profiles/<slug>.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.io import build_author_index, load_coauthor_network, load_papers
from common.metrics import (
    concept_vector,
    cosine,
    h_index,
    i10_index,
    pivot_score,
    role_guess,
    seminal_count,
    window_iter,
    year_series,
)
from common.names import slugify

WINDOW = 5


def build_author_first_year(papers: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in papers:
        y = p["year"]
        if not y:
            continue
        for a in p["authors"]:
            if a not in out or y < out[a]:
                out[a] = y
    return out


def detect_lineage(name: str, ps_idxs: list[int], papers: list[dict],
                   author_first_year: dict[str, int], first_year: int):
    """Infer likely_advisors and likely_students using 1st/last-author signal.

    A likely advisor C of `name`:
      - C is senior (active >= 5 years before name's first paper)
      - >=2 copubs in name's first 5 years where `name` is listed first
        (student-as-first-author convention)
      - C often appears in those papers (seniors on those papers)

    A likely student S of `name`:
      - S is junior (S's first atlas-paper year is >= name.first_year + 5)
      - >=2 copubs in S's first 5 years with `name`
      - S is first author in those papers in most cases
    """
    import collections as _c
    our_papers = [papers[i] for i in ps_idxs]

    # --- Likely advisors (based on our first 5 years as first-author)
    early_end = first_year + 5
    early_first_author = [
        p for p in our_papers
        if p["year"] and first_year <= p["year"] <= early_end
        and p["authors"] and p["authors"][0] == name
    ]
    advisor_signal = _c.Counter()
    advisor_last_count = _c.Counter()
    for p in early_first_author:
        for pos, a in enumerate(p["authors"]):
            if a == name:
                continue
            advisor_signal[a] += 1
            if pos == len(p["authors"]) - 1:
                advisor_last_count[a] += 1

    likely_advisors = []
    for c, cnt in advisor_signal.items():
        if cnt < 2:
            continue
        adv_start = author_first_year.get(c, 9999)
        if first_year - adv_start < 5:
            continue  # not senior enough
        total_copubs = sum(1 for p in our_papers if c in p["authors"])
        likely_advisors.append({
            "name": c,
            "advisor_active_from": adv_start,
            "early_copubs_as_our_first_author": cnt,
            "advisor_last_author_count": advisor_last_count.get(c, 0),
            "total_copubs": total_copubs,
        })
    likely_advisors.sort(key=lambda x: (
        -x["advisor_last_author_count"],
        -x["early_copubs_as_our_first_author"],
        -x["total_copubs"],
    ))

    # --- Likely students (based on their first 5 years, we as senior)
    all_coauthors = _c.Counter()
    for p in our_papers:
        for a in p["authors"]:
            if a != name:
                all_coauthors[a] += 1

    likely_students = []
    for c, total_cp in all_coauthors.items():
        if total_cp < 2:
            continue
        stu_start = author_first_year.get(c, 9999)
        if stu_start - first_year < 5:
            continue  # not junior enough
        stu_end = stu_start + 5
        c_early = [p for p in our_papers
                   if p["year"] and stu_start <= p["year"] <= stu_end
                   and c in p["authors"]]
        if len(c_early) < 2:
            continue
        student_first_author_count = sum(
            1 for p in c_early if p["authors"] and p["authors"][0] == c
        )
        if student_first_author_count < 1:
            continue
        we_last_author_count = sum(
            1 for p in c_early if p["authors"] and p["authors"][-1] == name
        )
        last_copub_year = max(p["year"] for p in our_papers if c in p["authors"] and p["year"])
        likely_students.append({
            "name": c,
            "student_first_year": stu_start,
            "copubs_in_first_5yr": len(c_early),
            "total_copubs": total_cp,
            "student_first_author_count": student_first_author_count,
            "we_last_author_count": we_last_author_count,
            "last_copub_year": last_copub_year,
        })
    likely_students.sort(key=lambda x: (
        -x["we_last_author_count"],
        -x["student_first_author_count"],
        -x["total_copubs"],
    ))

    return likely_advisors, likely_students


def build_profile(name: str, papers: list[dict], author_idx: dict,
                  coauth_node_map: dict, author_first_year: dict,
                  slug: str | None = None) -> dict:
    ps_idxs = author_idx.get(name)
    if not ps_idxs:
        return {"name": name, "error": "not_found"}
    ps = [papers[i] for i in ps_idxs]
    ps.sort(key=lambda p: (p["year"], p["title"]))
    years = [p["year"] for p in ps if p["year"] > 0]
    if not years:
        return {"name": name, "error": "no_year"}
    first_year, last_year = min(years), max(years)

    # Per-paper projection with role
    paper_rows = []
    for p in ps:
        paper_rows.append({
            "year": p["year"],
            "venue": p["venue"],
            "title": p["title"],
            "cites": p["cites"],
            "n_authors": len(p["authors"]),
            "role": role_guess(name, p["authors"]),
            "concepts": p["concepts"][:5],
            "doi": p["doi"],
            "coauthors": [a for a in p["authors"] if a != name],
        })
    cites_all = [p["cites"] for p in ps]

    # Milestones
    milestones = {
        "first_paper": {"year": ps[0]["year"], "title": ps[0]["title"]},
    }
    for thr in (100, 500, 1000):
        hit = next((p for p in ps if p["cites"] >= thr), None)
        if hit:
            milestones[f"first_{thr}cite"] = {
                "year": hit["year"], "title": hit["title"], "cites": hit["cites"],
                "gap_from_first": hit["year"] - first_year,
            }
    # Peak year = year producing the single most-cited paper
    peak_paper = max(ps, key=lambda p: p["cites"])
    milestones["peak_paper"] = {
        "year": peak_paper["year"], "title": peak_paper["title"],
        "cites": peak_paper["cites"],
    }

    # Topic / venue / collab evolution by 5y window
    windows_topic = []
    windows_venue = []
    windows_collab = []
    for ws, we in window_iter(first_year, last_year, WINDOW):
        win_ps = [p for p in ps if ws <= p["year"] <= we]
        if not win_ps:
            continue
        cv = concept_vector(win_ps)
        top_concepts = sorted(cv.items(), key=lambda x: -x[1])[:5]
        windows_topic.append({
            "start": ws, "end": we, "n_papers": len(win_ps),
            "top_concepts": [{"c": c, "w": round(w, 3)} for c, w in top_concepts],
            "_vec": cv,
        })
        venue_mix = collections.Counter(p["venue"] for p in win_ps)
        windows_venue.append({
            "start": ws, "end": we,
            "mix": dict(venue_mix.most_common()),
        })
        coauth_counter = collections.Counter()
        n_auth_per_paper = []
        for p in win_ps:
            n_auth_per_paper.append(len(p["authors"]))
            for a in p["authors"]:
                if a != name:
                    coauth_counter[a] += 1
        windows_collab.append({
            "start": ws, "end": we,
            "mean_n_authors": round(statistics.mean(n_auth_per_paper), 2),
            "unique_coauthors": len(coauth_counter),
            "top_coauthors": coauth_counter.most_common(5),
        })

    topic_windows_for_pivot = [((w["start"], w["end"]), w["_vec"]) for w in windows_topic]
    pivot = pivot_score(topic_windows_for_pivot)

    # Strip internal vectors before serialize
    for w in windows_topic:
        w.pop("_vec", None)

    # Repeat coauthors (>=3 copublications)
    all_coauth = collections.Counter()
    coauth_first_year = {}
    coauth_last_year = {}
    for p in ps:
        for a in p["authors"]:
            if a == name:
                continue
            all_coauth[a] += 1
            coauth_first_year[a] = min(coauth_first_year.get(a, 9999), p["year"] or 9999)
            coauth_last_year[a] = max(coauth_last_year.get(a, 0), p["year"] or 0)

    top_repeat = [
        {"name": a, "count": c,
         "first_year": coauth_first_year[a],
         "last_year": coauth_last_year[a]}
        for a, c in all_coauth.most_common(15)
    ]

    # Academic lineage (1st/last-author heuristic over first 5 years)
    likely_advisors, likely_students = detect_lineage(
        name, ps_idxs, papers, author_first_year, first_year
    )

    # Role distribution
    role_counts = collections.Counter(p["role"] for p in paper_rows)

    # Per-year time series over full career
    yseries = year_series(ps, first_year, last_year)

    # Citation half-life: median age of the citations received.
    # Proxy: weight each paper by cites; compute weighted median of (current_year - paper_year).
    current_year = max(last_year, 2026)
    cite_ages = []
    for p in ps:
        if p["year"] > 0 and p["cites"] > 0:
            cite_ages.extend([current_year - p["year"]] * p["cites"])
    citation_half_life = statistics.median(cite_ages) if cite_ages else None

    # Bursts: years with >2 SD above mean on papers OR cumulative cites attributed in that year
    ys = sorted(yseries)
    paper_counts = [yseries[y]["n"] for y in ys]
    cite_sums = [yseries[y]["cites"] for y in ys]
    def zflag(values):
        if len(values) < 5:
            return set()
        m = statistics.mean(values)
        sd = statistics.pstdev(values) or 1
        return {ys[i] for i, v in enumerate(values) if (v - m) / sd >= 2.0}
    bursts = {
        "productivity": sorted(zflag(paper_counts)),
        "impact": sorted(zflag(cite_sums)),
    }

    # Top 10 blockbusters
    blockbusters = sorted(paper_rows, key=lambda r: -r["cites"])[:10]

    # Solo → team drift: compare first-decade vs last-decade mean author counts
    def mean_n_auth(low, high):
        xs = [len(p["authors"]) for p in ps if low <= p["year"] <= high]
        return round(statistics.mean(xs), 2) if xs else None
    early_end = min(first_year + 9, last_year)
    late_start = max(last_year - 9, first_year)
    team_drift = {
        "early_window": [first_year, early_end],
        "early_mean_n_authors": mean_n_auth(first_year, early_end),
        "late_window": [late_start, last_year],
        "late_mean_n_authors": mean_n_auth(late_start, last_year),
    }

    return {
        "name": name,
        "slug": slug or slugify(name),
        "career_stats": {
            "first_year": first_year,
            "last_year": last_year,
            "span": last_year - first_year + 1,
            "total_papers": len(ps),
            "total_cites": sum(cites_all),
            "h_index": h_index(cites_all),
            "i10_index": i10_index(cites_all),
            "seminal_count": seminal_count(cites_all, 500),
            "max_cites_single_paper": max(cites_all),
        },
        "role_distribution": dict(role_counts),
        "milestones": milestones,
        "year_series": yseries,
        "topic_windows": windows_topic,
        "venue_windows": windows_venue,
        "collab_windows": windows_collab,
        "pivot_score": round(pivot, 3),
        "top_repeat_coauthors": top_repeat,
        "likely_advisors": likely_advisors[:5],
        "likely_students": likely_students,
        "team_drift": team_drift,
        "citation_half_life_years": citation_half_life,
        "bursts": bursts,
        "blockbusters": blockbusters,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="if omitted, process all from top_researchers.json")
    ap.add_argument("--top", default="analysis/top_researchers.json")
    ap.add_argument("--out-dir", default="analysis/profiles")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("Loading papers...", file=sys.stderr)
    papers = load_papers()
    author_idx = build_author_index(papers)
    author_first_year = build_author_first_year(papers)
    coauth = load_coauthor_network()
    coauth_node_map = {n["label"]: n for n in coauth["nodes"]}

    if args.name:
        targets = [{"name": args.name, "slug": slugify(args.name)}]
    else:
        with open(args.top, encoding="utf-8") as f:
            top = json.load(f)
        targets = [{"name": t["name"], "slug": t["slug"]} for t in top["top"]]

    for t in targets:
        print(f"  extracting {t['name']}...", file=sys.stderr)
        prof = build_profile(t["name"], papers, author_idx, coauth_node_map,
                             author_first_year, slug=t["slug"])
        out = os.path.join(args.out_dir, f"{t['slug']}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(prof, f, ensure_ascii=False, indent=2)
        print(f"    -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
