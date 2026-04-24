# Robo · Careers

People-side companion to [robopaper-atlas](https://github.com/gisbi-kim/robopaper-atlas).
100 trajectories of robotics masters — career archetypes, timing distributions, mentor→student lineage.

🔗 **Live**: https://gisbi-kim.github.io/robo-careers/

## What's inside

- **Top 100** researchers ranked by a composite z-score of total citations, h-index, blockbuster (≥500 cites) count, career span, and coauthor-network hub degree.
- **Career archetypes** via KMeans over normalized per-year citation curves.
- **Timing distributions** — years to first 100/500/1000+ cite paper, peak position, total span.
- **Topic dominance** — which master contributed most substantively to each OpenAlex concept.
- **Academic lineage** — likely PhD advisors and students inferred from first-author / last-author co-authorship patterns over each person's first 5 years.
- **Per-person auto-generated narrative** (EN + KO) with career lessons.
- **Cross-cutting meta-lessons** (EN + KO).

## Data artifacts

| Path | Content |
|---|---|
| `analysis/top_researchers.json` | Composite ranking of all 1,192 eligible authors; top 100 pulled forward. |
| `analysis/profiles/*.json` | Per-researcher deep profile (career_stats, milestones, topic_windows, collab_windows, likely_advisors, likely_students, blockbusters, insights.ko/en, …). |
| `analysis/meta.json` | Cross-cutting analysis: archetypes, timing distributions, topic_dominance, dynasty_ranking, lineage_edges_in_topN, cross_lessons.ko/en. |

## Regenerate

Requires `robopaper-atlas` cloned as a sibling at `./robopaper-atlas/`.

```bash
git clone https://github.com/gisbi-kim/robopaper-atlas.git
pip install pandas numpy scikit-learn

python scripts/00_select_top.py --k 100
python scripts/01_extract_profile.py
python scripts/02_compare.py
python scripts/03_distill.py
python scripts/04_build_html.py
```

Pipeline is modular — each phase writes JSON, next phase reads. Phase 2 is independent per-person and can be parallelized.

## Language

The HTML defaults to English. Append `#ko` to the URL for Korean:
`https://gisbi-kim.github.io/robo-careers/#ko`

## Credits

- [robopaper-atlas](https://github.com/gisbi-kim/robopaper-atlas) — the underlying 81,680-paper corpus (DBLP + OpenAlex).
- Chart.js for visualization.
