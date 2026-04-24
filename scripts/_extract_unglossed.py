"""Extract the unique phase-title phrases that fall to paper-fallback,
with their best-match paper title and abstract — so Claude (or a human)
can hand-write a one-line research-area gloss for each.

Output: analysis/_unglossed_phrases.json, with:
{
  "spherical spatial mechanisms": {
    "prettified": "Spherical Spatial Mechanisms",
    "seen_in":   ["Frank C. Park 1991—1995"],
    "paper_title": "On the optimal kinematic design of spherical and spatial mechanisms",
    "venue": "ICRA",
    "year": 1994,
    "cites": 5,
    "abstract": "..."
  },
  ...
}
"""
from __future__ import annotations

import json
import os
import sys
from glob import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.io import build_author_index, load_enriched, load_papers
from common.phrases import build_global_idf, distinctive_phrases, prettify
from common.glossary import lookup_phrases


PROFILES_DIR = "analysis/profiles"
OUT = "analysis/_unglossed_phrases.json"
WINDOW = 5


def main():
    print("Loading...", file=sys.stderr)
    papers = load_papers()
    author_idx = build_author_index(papers)
    idf, max_idf = build_global_idf(papers)
    enriched = load_enriched()

    out: dict = {}

    for fp in sorted(glob(os.path.join(PROFILES_DIR, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            prof = json.load(f)
        name = prof["name"]
        windows = prof.get("topic_windows", [])
        name_idxs = author_idx.get(name, [])
        author_papers = [papers[i] for i in name_idxs]

        for win in windows:
            ys, ye = win["start"], win["end"]
            win_papers = [p for p in author_papers if p.get("year") and ys <= p["year"] <= ye]
            raw_phrases = distinctive_phrases(win_papers, idf, max_idf, top_k=6)
            pretty = [prettify(p) for p in raw_phrases]
            # Only look at the phase-title slots — top 2
            title_phrases = pretty[:2]

            # Which of the TOP-2 phrases does the curated glossary already
            # cover on its own? We mirror the production build behavior.
            top2_hits = lookup_phrases(title_phrases, "en", max_entries=4)
            covered_term_tokens = [set(h["term"].lower().replace("-", " ").split())
                                   for h in top2_hits]

            for phr in title_phrases:
                phr_lower = phr.lower()
                if phr_lower in out:
                    out[phr_lower]["seen_in"].append(f"{name} {ys}-{ye}")
                    continue
                phr_tokens = set(phr_lower.replace("-", " ").split())
                # Skip if this phrase shares >=one content word with any
                # already-matched glossary term.
                if any(len(phr_tokens & ct) >= 1 for ct in covered_term_tokens):
                    continue

                # Find the best paper in window whose title contains all tokens
                filter_tokens = [t for t in phr_lower.replace("-", " ").split() if len(t) > 1]
                if not filter_tokens:
                    continue
                candidates = []
                for p in win_papers:
                    title_l = (p.get("title") or "").lower().replace("-", " ")
                    if all(tok in title_l for tok in filter_tokens):
                        candidates.append(p)
                if not candidates:
                    continue
                best = max(candidates, key=lambda x: x.get("cites", 0))
                doi = (best.get("doi") or "").lower()
                abstract = enriched.get(doi, {}).get("abstract", "")
                out[phr_lower] = {
                    "prettified": phr,
                    "seen_in": [f"{name} {ys}-{ye}"],
                    "paper_title": best.get("title"),
                    "venue": best.get("venue"),
                    "year": best.get("year"),
                    "cites": best.get("cites"),
                    "abstract": abstract[:800] if abstract else "",
                }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(out)} unique unglossed phrases to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
