"""Dry-run: score all 10 candidate theme signals for every profile.

Prints:
  - per-theme fire rate + top/bottom researchers
  - per-researcher top-3 theme selection
  - diversity table: how many unique (theme-A, theme-B, theme-C) combos appear
"""
from __future__ import annotations

import collections
import json
import math
import os
import statistics
import sys
from glob import glob


PROFILES_DIR = "analysis/profiles"
TOP_PATH = "analysis/top_researchers.json"
META_PATH = "analysis/meta.json"

# Theme fire threshold — score below this means theme is not distinctive
FIRE_THRESHOLD = 0.35


def load_profiles():
    profs = []
    for fp in sorted(glob(os.path.join(PROFILES_DIR, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            profs.append(json.load(f))
    with open(TOP_PATH, encoding="utf-8") as f:
        top = json.load(f)
    rank_map = {x["slug"]: x for x in top["top"]}
    for p in profs:
        p["_rank_info"] = rank_map.get(p["slug"], {})
    return profs


# ---------- 10 theme scoring functions ----------
# Each returns: (score: float 0..1, label: str, detail: dict)
# Higher score = more distinctive. 0 = unremarkable.

JOURNAL_VENUES = {"T-RO", "IJRR", "RA-L", "T-Mech", "Sci-Rob", "SoRo"}


def score_role_signature(p):
    rd = p.get("role_distribution", {})
    total = sum(rd.values()) or 1
    fracs = {k: v / total for k, v in rd.items()}
    last = fracs.get("last", 0)
    first = fracs.get("first", 0)
    solo = fracs.get("solo", 0)
    # score = how extreme any role ratio is
    candidates = []
    if last >= 0.70:
        candidates.append((min((last - 0.5) * 2.5, 1.0), f"last_author={last:.0%}"))
    if first >= 0.30 and p["career_stats"]["span"] >= 15:
        candidates.append((min((first - 0.15) * 3, 1.0), f"still_first_author={first:.0%}"))
    if solo >= 0.12:
        candidates.append((min(solo * 3, 1.0), f"solo_writer={solo:.0%}"))
    if not candidates:
        return 0.0, "", {}
    s, lbl = max(candidates)
    return s, "role_signature", {"label": lbl, "fracs": {k: round(v,2) for k,v in fracs.items()}}


def score_venue_evolution(p):
    vws = p.get("venue_windows", [])
    if len(vws) < 3:
        return 0.0, "", {}
    def journal_share(w):
        mix = w.get("mix", {})
        tot = sum(mix.values()) or 1
        return sum(v for k, v in mix.items() if k in JOURNAL_VENUES) / tot
    early = statistics.mean(journal_share(w) for w in vws[:2])
    late = statistics.mean(journal_share(w) for w in vws[-2:])
    shift = late - early
    # shift of 0.3+ is notable
    score = min(abs(shift) * 2.5, 1.0) if abs(shift) >= 0.2 else 0.0
    direction = "conf_to_journal" if shift > 0 else "journal_to_conf"
    return score, "venue_evolution", {"early": round(early,2), "late": round(late,2), "dir": direction}


def score_blockbuster_concentration(p):
    bbs = p.get("blockbusters", [])
    if len(bbs) < 3:
        return 0.0, "", {}
    years = [b["year"] for b in bbs[:10] if b.get("year")]
    cites = [b["cites"] for b in bbs[:10]]
    if not years or not cites:
        return 0.0, "", {}
    # concentration: low stdev = high concentration
    yr_spread = max(years) - min(years) + 1
    span = p["career_stats"]["span"]
    concentration = 1 - (yr_spread / span) if span > 0 else 0
    # single-dominant ratio
    ratio = cites[0] / cites[1] if len(cites) > 1 and cites[1] > 0 else 1.0
    # Two distinctive regimes:
    #   - all 10 within <= 5y  → "concentrated era"
    #   - top-1 >> top-2 (ratio>=2.5) → "single dominant"
    score = 0.0
    label = ""
    if yr_spread <= 5 and len(years) >= 5:
        score = 0.9
        label = f"all_in_{yr_spread}y"
    elif ratio >= 2.5:
        score = min((ratio - 1.5) / 3, 1.0)
        label = f"single_dominant_x{ratio:.1f}"
    elif yr_spread >= 20:
        score = 0.5
        label = f"spread_over_{yr_spread}y"
    return score, "blockbuster_concentration", {"yr_spread": yr_spread, "ratio": round(ratio, 2), "label": label}


def score_peak_position(p):
    ms = p.get("milestones", {})
    cs = p["career_stats"]
    peak = ms.get("peak_paper")
    if not peak or not peak.get("year"):
        return 0.0, "", {}
    rel = (peak["year"] - cs["first_year"]) / max(cs["span"] - 1, 1)
    if 0.25 <= rel <= 0.66:
        return 0.0, "", {"rel": round(rel, 2)}  # unremarkable
    # score: distance from middle
    s = min(abs(rel - 0.5) * 2, 1.0)
    return s, "peak_position", {"rel": round(rel, 2), "when": "early" if rel < 0.25 else "late"}


def score_citation_half_life(p):
    hl = p.get("citation_half_life_years")
    if hl is None:
        return 0.0, "", {}
    # median is around ~8-10y; extreme is <5 or >15
    diff = abs(hl - 10)
    score = min(diff / 10, 1.0)
    return score, "citation_half_life", {"hl": hl}


def score_productivity_rhythm(p):
    ys = p.get("year_series", {})
    if not ys:
        return 0.0, "", {}
    years = sorted(int(y) for y in ys.keys())
    counts = [ys[str(y)]["n"] if str(y) in ys else ys[y]["n"] for y in years]
    if len(counts) < 5:
        return 0.0, "", {}
    mean = statistics.mean(counts)
    if mean == 0:
        return 0.0, "", {}
    sd = statistics.pstdev(counts)
    cv = sd / mean  # coefficient of variation
    # trend: linear regression slope sign
    n = len(years)
    xs = list(range(n))
    xbar = (n - 1) / 2
    ybar = sum(counts) / n
    num = sum((xs[i] - xbar) * (counts[i] - ybar) for i in range(n))
    den = sum((xs[i] - xbar) ** 2 for i in range(n)) or 1
    slope = num / den
    bursts = p.get("bursts", {})
    n_bursts = len(bursts.get("productivity", [])) + len(bursts.get("impact", []))
    # Patterns:
    #   monotonic rise: slope high, cv low-mid
    #   bursty: cv very high, n_bursts >= 2
    #   late surge: slope strongly positive at end — approximate via last-third mean vs middle-third
    thirds = n // 3 or 1
    first_third = sum(counts[:thirds]) / thirds
    last_third = sum(counts[-thirds:]) / thirds
    label = ""
    score = 0.0
    if cv >= 1.0 and n_bursts >= 2:
        score = min(cv / 1.5, 1.0)
        label = f"bursty(cv={cv:.2f},nb={n_bursts})"
    elif last_third >= first_third * 3 and first_third >= 0.5:
        score = 0.7
        label = f"late_surge({first_third:.1f}→{last_third:.1f})"
    elif first_third >= last_third * 2 and last_third > 0:
        score = 0.55
        label = f"early_heavy({first_third:.1f}→{last_third:.1f})"
    elif cv < 0.5 and n >= 10:
        score = 0.35
        label = f"metronome(cv={cv:.2f})"
    return score, "productivity_rhythm", {"cv": round(cv, 2), "slope": round(slope, 2), "n_bursts": n_bursts, "label": label}


def score_cross_venue_breadth(p):
    vws = p.get("venue_windows", [])
    venues = set()
    for w in vws:
        for v in w.get("mix", {}).keys():
            if v:
                venues.add(v)
    n = len(venues)
    if n >= 7:
        return min((n - 5) / 4, 1.0), "cross_venue_generalist", {"n": n, "venues": sorted(venues)}
    if n <= 2:
        return 0.6, "cross_venue_specialist", {"n": n, "venues": sorted(venues)}
    return 0.0, "", {"n": n}


def score_collaboration_rhythm(p):
    tops = p.get("top_repeat_coauthors", [])
    if len(tops) < 3:
        return 0.0, "", {}
    total = sum(t["count"] for t in tops)
    top3 = sum(t["count"] for t in tops[:3])
    top3_share = top3 / total if total > 0 else 0
    top1 = tops[0]["count"]
    # Fixed partner:
    if top3_share >= 0.55 and top1 >= 10:
        return min((top3_share - 0.4) * 3, 1.0), "fixed_partners", {
            "top3_share": round(top3_share, 2),
            "top1": top1,
            "partners": [t["name"] for t in tops[:3]],
        }
    # Rotating: top1 <= 4 copubs but many entries → many one-shot collaborators
    if top1 <= 4 and len(tops) >= 10:
        return 0.5, "rotating_collaborators", {"top1": top1, "n_partners": len(tops)}
    return 0.0, "", {"top3_share": round(top3_share, 2)}


def score_community_centrality(p, hub_rank_of_pool):
    ri = p.get("_rank_info", {})
    hub_rank = ri.get("rank_hub_degree")
    hub = ri.get("hub_degree")
    if hub_rank is None or hub is None:
        return 0.0, "", {}
    # top 5% of natural pool or bottom 5% (relative to 1196-sized pool)
    if hub_rank <= 12:
        score = min((13 - hub_rank) / 12, 1.0)
        return score, "community_hub", {"hub_rank": hub_rank, "hub": hub}
    if hub <= 15:
        return 0.4, "community_periphery", {"hub_rank": hub_rank, "hub": hub}
    return 0.0, "", {"hub_rank": hub_rank}


def score_lineage(p, meta_dynasty):
    students = p.get("likely_students", [])
    advisors = p.get("likely_advisors", [])
    topN_students = meta_dynasty.get(p["name"], 0)
    n = len(students)
    score = 0.0
    label = ""
    if topN_students >= 2:
        score = 0.95
        label = f"dynasty_x{topN_students}"
    elif topN_students == 1:
        score = 0.75
        label = "dynasty_x1"
    elif n >= 30:
        score = 0.6
        label = f"n_students={n}"
    elif n >= 15:
        score = 0.4
        label = f"n_students={n}"
    elif advisors and n == 0:
        score = 0.35
        label = "advisor_only"
    return score, "lineage", {"label": label, "n_students": n, "topN_students": topN_students}


THEMES = [
    ("role_signature", score_role_signature),
    ("venue_evolution", score_venue_evolution),
    ("blockbuster_concentration", score_blockbuster_concentration),
    ("peak_position", score_peak_position),
    ("citation_half_life", score_citation_half_life),
    ("productivity_rhythm", score_productivity_rhythm),
    ("cross_venue_breadth", score_cross_venue_breadth),
    ("collaboration_rhythm", score_collaboration_rhythm),
    ("community_centrality", None),  # handled below
    ("lineage", None),  # handled below
]


def main():
    profiles = load_profiles()
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    dynasty_map = {x["name"]: x["students_in_topN"] for x in meta.get("dynasty_ranking", [])}

    scores = {}  # name -> {theme_key: (score, detail)}
    for p in profiles:
        per = {}
        for key, fn in THEMES:
            if fn is not None:
                s, lbl, det = fn(p)
            elif key == "community_centrality":
                s, lbl, det = score_community_centrality(p, None)
            elif key == "lineage":
                s, lbl, det = score_lineage(p, dynasty_map)
            else:
                s, lbl, det = 0.0, "", {}
            per[key] = {"score": round(s, 3), "label": lbl, "detail": det}
        scores[p["name"]] = per

    # Aggregate: fire rate per theme
    print("=" * 76)
    print(f"Fire rates (score > {FIRE_THRESHOLD}):")
    print("=" * 76)
    for key, _ in THEMES:
        fires = sum(1 for s in scores.values() if s[key]["score"] > FIRE_THRESHOLD)
        means = [s[key]["score"] for s in scores.values()]
        print(f"  {key:<28s} fires {fires:3d}/{len(profiles):3d} "
              f"({fires/len(profiles):.0%})  mean={statistics.mean(means):.2f}  "
              f"max={max(means):.2f}")

    # Per-person top-3 selection
    print()
    print("=" * 76)
    print("Per-researcher top-3 themes (by score):")
    print("=" * 76)
    for p in profiles:
        ri = p.get("_rank_info", {})
        rnk = ri.get("rank", "?")
        per = scores[p["name"]]
        ranked = sorted(per.items(), key=lambda kv: -kv[1]["score"])
        top3 = [(k, v["score"], v["detail"].get("label", "") or v["label"]) for k, v in ranked[:3] if v["score"] > 0]
        summary = "  | ".join(f"{k}={s:.2f}" for k, s, _ in top3)
        print(f"  #{rnk:>3}  {p['name']:<32s}  {summary}")

    # Distribution of top-3 combinations
    combos = collections.Counter()
    first_picks = collections.Counter()
    for p in profiles:
        per = scores[p["name"]]
        ranked = sorted(per.items(), key=lambda kv: -kv[1]["score"])
        top3_keys = tuple(k for k, v in ranked[:3] if v["score"] > 0)
        combos[top3_keys] += 1
        if top3_keys:
            first_picks[top3_keys[0]] += 1

    print()
    print("=" * 76)
    print("Theme-as-top-1 distribution:")
    print("=" * 76)
    for k, n in first_picks.most_common():
        print(f"  {k:<28s} {n:3d} researchers as their top-1")

    print()
    print(f"Unique top-3 combos: {len(combos)} / {len(profiles)}")
    print("Most repeated top-3 combos:")
    for combo, n in combos.most_common(10):
        if n >= 2:
            print(f"  x{n}  {' > '.join(combo) if combo else '(all below threshold)'}")

    # Save to JSON
    out = "analysis/_theme_probe.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)
    print(f"\nWrote per-person scores to {out}")


if __name__ == "__main__":
    main()
