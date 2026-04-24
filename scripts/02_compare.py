"""Phase 3: cross-cutting analysis across all profiles.

Output: analysis/meta.json
  - distributions (first-blockbuster gap, etc.)
  - career arc archetypes via KMeans on normalized output curves
  - topic dominance map
  - generational cohorts
  - conference -> journal transition age (if any)
"""
from __future__ import annotations

import collections
import glob
import json
import os
import statistics
import sys

import numpy as np
from sklearn.cluster import KMeans

PROFILES_DIR = "analysis/profiles"
OUT_PATH = "analysis/meta.json"

ARC_LEN = 40  # normalized career length in bins


def load_profiles() -> list[dict]:
    out = []
    for fp in sorted(glob.glob(os.path.join(PROFILES_DIR, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def normalized_arc(profile: dict, metric: str = "cites") -> np.ndarray:
    """Resample year_series to ARC_LEN bins in [0,1] career time."""
    ys = profile["year_series"]
    years = sorted(int(y) for y in ys.keys())
    if not years:
        return np.zeros(ARC_LEN)
    values = [ys[str(y)][metric] if isinstance(next(iter(ys)), str) else ys[y][metric]
              for y in years]
    # year_series keys are ints when written, become strings in json
    # handle both
    def get(y, m):
        v = ys.get(y)
        if v is None:
            v = ys.get(str(y))
        return v[m] if v else 0
    values = [get(y, metric) for y in years]
    arr = np.array(values, dtype=float)
    if arr.sum() == 0:
        return np.zeros(ARC_LEN)
    # Resample via linear interpolation onto ARC_LEN bins
    t_old = np.linspace(0, 1, len(arr))
    t_new = np.linspace(0, 1, ARC_LEN)
    resampled = np.interp(t_new, t_old, arr)
    resampled = resampled / resampled.sum()  # prob dist
    return resampled


def classify_archetype(centroid: np.ndarray) -> str:
    """Heuristic label from the cluster centroid shape."""
    early = centroid[: ARC_LEN // 3].sum()
    mid = centroid[ARC_LEN // 3 : 2 * ARC_LEN // 3].sum()
    late = centroid[2 * ARC_LEN // 3 :].sum()
    peak_pos = int(np.argmax(centroid)) / ARC_LEN
    if early > 0.5:
        return "early-blockbuster"
    if late > 0.5:
        return "late-bloomer"
    if mid > 0.45 and peak_pos > 0.35 and peak_pos < 0.65:
        return "mid-career-peak"
    spread = float(centroid.std())
    if spread < 0.02:
        return "steady-producer"
    return "multi-peak"


def main():
    profiles = load_profiles()
    print(f"Loaded {len(profiles)} profiles", file=sys.stderr)

    # --- Archetype clustering (on citation-curve shape)
    arcs = np.array([normalized_arc(p, "cites") for p in profiles])
    n_clusters = min(8, max(5, len(profiles) // 12))
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(arcs)
    centroids = km.cluster_centers_
    archetype_names = [classify_archetype(c) for c in centroids]
    # Resolve duplicate names
    seen = collections.Counter()
    unique_names = []
    for n in archetype_names:
        seen[n] += 1
        unique_names.append(n if seen[n] == 1 else f"{n}-{seen[n]}")

    archetype_assignments = []
    for p, lab in zip(profiles, labels):
        archetype_assignments.append({
            "name": p["name"],
            "slug": p["slug"],
            "cluster": int(lab),
            "archetype": unique_names[int(lab)],
        })

    archetypes = [
        {
            "cluster": i,
            "label": unique_names[i],
            "centroid": centroids[i].tolist(),
            "members": [a["name"] for a in archetype_assignments if a["cluster"] == i],
        }
        for i in range(n_clusters)
    ]

    # --- Timing distributions
    def safe_get(p, path, default=None):
        cur = p
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    gap_first_100 = []
    gap_first_500 = []
    gap_first_1000 = []
    peak_positions = []  # peak year / span
    spans = []
    for p in profiles:
        g100 = safe_get(p, ["milestones", "first_100cite", "gap_from_first"])
        g500 = safe_get(p, ["milestones", "first_500cite", "gap_from_first"])
        g1000 = safe_get(p, ["milestones", "first_1000cite", "gap_from_first"])
        if g100 is not None:
            gap_first_100.append(g100)
        if g500 is not None:
            gap_first_500.append(g500)
        if g1000 is not None:
            gap_first_1000.append(g1000)
        first_y = safe_get(p, ["career_stats", "first_year"])
        last_y = safe_get(p, ["career_stats", "last_year"])
        peak_y = safe_get(p, ["milestones", "peak_paper", "year"])
        if first_y and last_y and peak_y:
            span = last_y - first_y + 1
            spans.append(span)
            peak_positions.append(round((peak_y - first_y) / max(span - 1, 1), 3))

    def stats(xs):
        if not xs:
            return None
        return {
            "n": len(xs),
            "min": min(xs),
            "max": max(xs),
            "median": statistics.median(xs),
            "mean": round(statistics.mean(xs), 2),
            "values": xs,
        }

    timing = {
        "years_to_first_100cite": stats(gap_first_100),
        "years_to_first_500cite": stats(gap_first_500),
        "years_to_first_1000cite": stats(gap_first_1000),
        "peak_paper_relative_position": stats(peak_positions),
        "career_span_years": stats(spans),
    }

    # --- Topic dominance map
    topic_totals = collections.Counter()
    topic_contributors = collections.defaultdict(list)
    for p in profiles:
        contrib = collections.Counter()
        for w in p.get("topic_windows", []):
            for tc in w.get("top_concepts", []):
                contrib[tc["c"]] += tc["w"] * w["n_papers"]
        for c, v in contrib.items():
            topic_totals[c] += v
            topic_contributors[c].append((p["name"], round(v, 2)))

    topic_dominance = []
    for c, total in topic_totals.most_common(30):
        contributors = sorted(topic_contributors[c], key=lambda x: -x[1])[:5]
        topic_dominance.append({
            "concept": c,
            "total_weight": round(total, 2),
            "top_contributors": [{"name": n, "weight": w} for n, w in contributors],
        })

    # --- Generational cohorts
    cohorts = collections.defaultdict(list)
    for p in profiles:
        fy = safe_get(p, ["career_stats", "first_year"])
        if fy is None:
            continue
        decade = (fy // 10) * 10
        cohorts[decade].append({
            "name": p["name"],
            "first_year": fy,
            "total_cites": safe_get(p, ["career_stats", "total_cites"]),
            "h_index": safe_get(p, ["career_stats", "h_index"]),
            "pivot_score": p.get("pivot_score"),
        })
    cohort_summary = []
    for decade, members in sorted(cohorts.items()):
        cohort_summary.append({
            "decade": decade,
            "n": len(members),
            "members": [m["name"] for m in members],
            "median_h_index": statistics.median([m["h_index"] for m in members if m["h_index"]]) if members else None,
            "median_total_cites": statistics.median([m["total_cites"] for m in members if m["total_cites"]]) if members else None,
            "median_pivot_score": round(
                statistics.median([m["pivot_score"] for m in members if m["pivot_score"] is not None]), 3
            ) if members else None,
        })

    # --- Conf -> journal transition
    journal_venues = {"T-RO", "IJRR", "RA-L", "T-Mech", "Sci-Rob", "SoRo"}

    transitions = []
    for p in profiles:
        vws = p.get("venue_windows", [])
        crossed = None
        for w in vws:
            mix = w.get("mix", {})
            total = sum(mix.values()) or 1
            j_share = sum(v for k, v in mix.items() if k in journal_venues) / total
            if j_share >= 0.5:
                crossed = w["start"]
                break
        transitions.append({
            "name": p["name"],
            "first_year": safe_get(p, ["career_stats", "first_year"]),
            "journal_majority_from": crossed,
            "years_to_journal_majority": (crossed - safe_get(p, ["career_stats", "first_year"])) if crossed else None,
        })
    trans_gaps = [t["years_to_journal_majority"] for t in transitions if t["years_to_journal_majority"] is not None]
    transition_stats = stats(trans_gaps) if trans_gaps else None

    # --- Pivot score ranking
    pivot_rank = sorted(
        [{"name": p["name"], "pivot_score": p.get("pivot_score", 0)} for p in profiles],
        key=lambda x: -x["pivot_score"],
    )

    # --- Academic dynasty (who trained people who themselves made top-N?)
    names_in_topN = {p["name"] for p in profiles}

    student_adj = collections.defaultdict(list)   # mentor -> [(student, signals)]
    advisor_adj = collections.defaultdict(list)   # student -> [(advisor, signals)]
    for p in profiles:
        for s in p.get("likely_students", []):
            student_adj[p["name"]].append(s)
            if s["name"] in names_in_topN:
                advisor_adj[s["name"]].append({
                    "advisor": p["name"],
                    "we_last_author_count": s["we_last_author_count"],
                    "copubs_in_first_5yr": s["copubs_in_first_5yr"],
                })

    dynasty_ranking = []
    for p in profiles:
        m = p["name"]
        all_students = student_adj.get(m, [])
        topN_students = [s for s in all_students if s["name"] in names_in_topN]
        dynasty_ranking.append({
            "name": m,
            "total_likely_students": len(all_students),
            "students_in_topN": len(topN_students),
            "students_in_topN_names": [s["name"] for s in topN_students],
        })
    dynasty_ranking.sort(key=lambda x: (-x["students_in_topN"], -x["total_likely_students"]))

    # Cross-profile mentor-student adjacency (top-N only)
    lineage_edges = []  # list of {advisor, student, signals}
    for p in profiles:
        for s in p.get("likely_students", []):
            if s["name"] in names_in_topN:
                lineage_edges.append({
                    "advisor": p["name"],
                    "student": s["name"],
                    "we_last_author_count": s["we_last_author_count"],
                    "student_first_author_count": s["student_first_author_count"],
                    "copubs_in_first_5yr": s["copubs_in_first_5yr"],
                    "total_copubs": s["total_copubs"],
                    "student_first_year": s["student_first_year"],
                })

    meta = {
        "n_profiles": len(profiles),
        "arc_length": ARC_LEN,
        "archetypes": archetypes,
        "archetype_assignments": archetype_assignments,
        "timing_distributions": timing,
        "topic_dominance": topic_dominance,
        "generational_cohorts": cohort_summary,
        "venue_transitions": {
            "journal_venues": sorted(journal_venues),
            "per_person": transitions,
            "distribution": transition_stats,
        },
        "pivot_ranking": pivot_rank,
        "dynasty_ranking": dynasty_ranking,
        "lineage_edges_in_topN": lineage_edges,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH}", file=sys.stderr)

    # Console summary
    print("\n=== Archetypes ===", file=sys.stderr)
    for arc in archetypes:
        print(f"  [{arc['label']}] ({len(arc['members'])}): {', '.join(arc['members'])}",
              file=sys.stderr)
    print("\n=== Timing medians ===", file=sys.stderr)
    for k, v in timing.items():
        if v:
            print(f"  {k}: median={v['median']} range=({v['min']}-{v['max']}) n={v['n']}",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
