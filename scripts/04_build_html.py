"""Phase 5: build index.html (robo-careers) from profiles + meta.

Bilingual (EN default, KO via URL hash #ko or #kor). Static + Chart.js CDN only.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import sys


META_PATH = "analysis/meta.json"
PROFILES_DIR = "analysis/profiles"
OUT_PATH = "index.html"


def load_all():
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    profiles = []
    for fp in sorted(glob.glob(os.path.join(PROFILES_DIR, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            profiles.append(json.load(f))
    rank_map = {}
    top_path = "analysis/top_researchers.json"
    if os.path.exists(top_path):
        with open(top_path, encoding="utf-8") as f:
            t = json.load(f)
        rank_map = {x["slug"]: x for x in t["top"]}
    for p in profiles:
        p["_rank_info"] = rank_map.get(p["slug"], {})
    profiles.sort(key=lambda p: p["_rank_info"].get("rank", 999))
    return meta, profiles


CSS = r"""
:root {
  --ink: #1a1614;
  --paper: #f5f1ea;
  --paper-2: #ebe4d7;
  --rule: #1a1614;
  --accent: #c1440e;
  --accent-2: #2d4a3e;
  --muted: #6b6259;
  --highlight: #f4d35e;
  --card: #fbf8f1;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  background: var(--paper);
  color: var(--ink);
  font-family: 'Pretendard', 'Noto Serif KR', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  word-break: keep-all;
}

body {
  background-image:
    radial-gradient(circle at 20% 30%, rgba(193, 68, 14, 0.04) 0%, transparent 40%),
    radial-gradient(circle at 80% 70%, rgba(45, 74, 62, 0.04) 0%, transparent 40%);
  min-height: 100vh;
  padding: 40px 20px 96px;
}

.grain {
  position: fixed; inset: 0; pointer-events: none;
  opacity: 0.35; mix-blend-mode: multiply; z-index: 1;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/><feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.08 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
}

.container { max-width: 1280px; margin: 0 auto; position: relative; z-index: 2; }

.masthead {
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--ink);
  padding: 14px 0 12px;
  margin-bottom: 32px;
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 24px; flex-wrap: wrap;
}
.masthead .brand {
  font-family: 'Fraunces', 'Noto Serif KR', serif;
  font-weight: 900; font-style: italic;
  font-size: clamp(2rem, 4vw, 2.8rem);
  letter-spacing: -0.02em; line-height: 1;
}
.masthead .brand .amp { color: var(--accent); }
.masthead .meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.66rem; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--muted);
  text-align: right; line-height: 1.7;
  display: flex; flex-direction: column; gap: 1px;
  align-items: flex-end;
}
.masthead .meta-row { display: inline; white-space: normal; }
.masthead .meta .dot { color: var(--accent); margin: 0 6px; opacity: 0.5; }
.masthead .meta a { color: var(--accent); text-decoration: none; border-bottom: 1px dotted currentColor; }

.lang-tabs {
  display: inline-flex; align-items: center;
  gap: 2px; margin-left: 10px;
}
.lang-tab {
  padding: 2px 7px; cursor: pointer;
  text-decoration: none; color: var(--muted);
  border: 1px solid transparent;
  user-select: none; font-size: 0.64rem;
}
.lang-tab.active {
  color: var(--paper); background: var(--ink);
  border-color: var(--ink);
}
.lang-tab:not(.active):hover { color: var(--ink); border-color: var(--muted); }
.lang-sep { color: var(--muted); opacity: 0.35; font-size: 0.6rem; }

.hero {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 40px; margin-bottom: 56px;
  padding: 24px 0;
  border-bottom: 1px solid rgba(26,22,20,0.15);
}
.hero .kicker {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; text-transform: uppercase;
  letter-spacing: 0.12em; color: var(--accent-2);
  margin-bottom: 16px; display: inline-block;
}
.hero h1 {
  font-family: 'Noto Serif KR', 'Fraunces', serif;
  font-weight: 600; font-size: clamp(1.6rem, 3vw, 2.4rem);
  line-height: 1.25; letter-spacing: -0.01em;
}
.hero h1 em { font-style: italic; color: var(--accent); }
.hero-note {
  font-family: 'Noto Serif KR', serif;
  font-size: 0.95rem; color: var(--muted);
  align-self: end; border-left: 3px solid var(--accent); padding-left: 16px;
}

section { margin-bottom: 64px; }
section h2 {
  font-family: 'Noto Serif KR', 'Fraunces', serif;
  font-weight: 700; font-size: 1.6rem; letter-spacing: -0.01em;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--ink); padding-bottom: 10px;
}
section h2 .sub {
  color: var(--muted); font-size: 0.75rem;
  font-family: 'JetBrains Mono', monospace; letter-spacing: 0.1em;
  font-weight: 400;
}
section .section-desc {
  font-size: 0.9rem; color: var(--muted);
  margin: 12px 0 28px; max-width: 820px;
}

.rank-table {
  width: 100%; border-collapse: collapse;
  background: var(--card);
  font-size: 0.85rem;
  font-family: 'JetBrains Mono', monospace;
}
.rank-table th, .rank-table td {
  padding: 10px 12px; text-align: right;
  border-bottom: 1px solid rgba(26,22,20,0.08);
}
.rank-table th {
  text-align: right;
  text-transform: uppercase; font-size: 0.68rem; letter-spacing: 0.08em;
  color: var(--muted); background: var(--paper-2);
  cursor: pointer; user-select: none;
  position: sticky; top: 0;
}
.rank-table th:hover { color: var(--accent); }
.rank-table th.sort-asc::after { content: ' \25B2'; color: var(--accent); }
.rank-table th.sort-desc::after { content: ' \25BC'; color: var(--accent); }
.rank-table td.name { text-align: left; font-family: 'Noto Serif KR', serif; font-weight: 600; font-size: 0.92rem; }
.rank-table td.archetype {
  text-align: left; font-size: 0.7rem; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--accent-2);
}
.rank-table tbody tr:hover { background: var(--paper-2); }
.rank-table td.rank { color: var(--muted); width: 40px; }

.archetype-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px;
}
.archetype-card {
  background: var(--card);
  padding: 18px; border-top: 3px solid var(--accent);
}
.archetype-card h3 {
  font-family: 'Fraunces', serif;
  font-style: italic; font-size: 1.15rem;
  margin-bottom: 10px;
}
.archetype-card .members {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; color: var(--muted); line-height: 1.5;
}
.archetype-card .chart-box { position: relative; width: 100%; height: 80px; margin: 10px 0; }

.timing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
}
.timing-card {
  background: var(--card); padding: 18px;
  border-left: 3px solid var(--accent-2);
}
.timing-card .label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; text-transform: uppercase;
  color: var(--muted); letter-spacing: 0.08em;
  margin-bottom: 8px;
}
.timing-card .value {
  font-family: 'Fraunces', serif;
  font-size: 2.4rem; font-weight: 700;
  color: var(--accent); line-height: 1;
}
.timing-card .value .unit {
  font-size: 0.9rem; color: var(--muted); margin-left: 6px;
}
.timing-card .range {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; color: var(--muted);
  margin-top: 6px;
}
.timing-card .chart-box { position: relative; width: 100%; height: 70px; margin-top: 14px; }

.profile-filter {
  margin-bottom: 24px; display: flex; gap: 12px; align-items: center;
  flex-wrap: wrap;
}
.profile-filter input {
  font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
  padding: 8px 12px; min-width: 220px;
  border: 1px solid var(--ink); background: var(--card);
  color: var(--ink); outline: none;
}
.profile-filter input:focus { border-color: var(--accent); }
.filter-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 6px 12px; cursor: pointer; user-select: none;
  border: 1px solid var(--ink); background: var(--card); color: var(--ink);
}
.chip.active { background: var(--ink); color: var(--paper); }
.chip:hover:not(.active) { background: var(--paper-2); }

.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 28px;
}
.profile-card.hidden { display: none; }
.profile-card {
  background: var(--card);
  padding: 26px;
  position: relative;
  border-top: 3px solid var(--ink);
  display: flex; flex-direction: column; gap: 16px;
}
.profile-head .rank-badge {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; color: var(--muted);
  letter-spacing: 0.1em;
}
.profile-head h3 {
  font-family: 'Fraunces', serif;
  font-size: 1.6rem; font-weight: 700;
  letter-spacing: -0.02em; margin-top: 4px;
}
.profile-head .archetype-tag {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--accent); margin-top: 4px;
}
.profile-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 12px 0;
  border-top: 1px solid rgba(26,22,20,0.12);
  border-bottom: 1px solid rgba(26,22,20,0.12);
}
.profile-stats .stat { text-align: center; }
.profile-stats .stat .k {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem; text-transform: uppercase;
  color: var(--muted); letter-spacing: 0.08em;
}
.profile-stats .stat .v {
  font-family: 'Fraunces', serif;
  font-size: 1.3rem; font-weight: 700;
  color: var(--ink);
}
.profile-card .spark-box { position: relative; width: 100%; height: 90px; }
.profile-section { font-size: 0.85rem; }
.profile-section h4 {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--accent-2);
  margin-bottom: 8px;
}
.profile-section h4 .soft {
  font-weight: 400; text-transform: none;
  color: var(--muted); letter-spacing: 0;
  margin-left: 4px;
}
.profile-section ul { list-style: none; padding-left: 0; }
.profile-section li { margin-bottom: 4px; }
.profile-section .peak {
  font-family: 'Noto Serif KR', serif; font-size: 0.88rem;
  background: var(--paper-2); padding: 10px 12px; border-left: 2px solid var(--accent);
  line-height: 1.5;
}
.profile-section .peak .meta {
  font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
  color: var(--muted); margin-top: 4px;
}
.tag {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  background: var(--paper-2); color: var(--accent-2);
  padding: 2px 8px; margin: 2px 4px 2px 0;
  border-radius: 2px;
}
.narrative {
  font-family: 'Noto Serif KR', serif;
  font-size: 0.9rem; line-height: 1.65;
  color: var(--ink);
  padding: 12px 0;
  border-top: 1px dashed rgba(26,22,20,0.2);
}
.narrative p { margin-bottom: 8px; }
.lessons {
  font-family: 'Noto Serif KR', serif; font-size: 0.88rem;
  background: rgba(244,211,94,0.14);
  padding: 12px 14px; border-left: 3px solid var(--highlight);
}
.lessons h4 {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--muted);
  margin-bottom: 6px;
}
.lessons li { margin-left: 18px; margin-bottom: 4px; }

.cross-lessons {
  background: var(--card);
  padding: 32px;
  border-top: 3px solid var(--accent);
}
.cross-lessons ol {
  font-family: 'Noto Serif KR', serif;
  font-size: 1.0rem; line-height: 1.75;
  padding-left: 22px;
}
.cross-lessons li { margin-bottom: 12px; }
.cross-lessons li strong { color: var(--accent); }

.topic-dom {
  display: grid; gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}
.topic-dom .t {
  background: var(--card); padding: 12px 14px;
  border-left: 3px solid var(--accent-2);
  font-size: 0.85rem;
}
.topic-dom .t .c {
  font-family: 'Fraunces', serif; font-weight: 700;
  font-size: 1.05rem;
}
.topic-dom .t .who {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; color: var(--muted);
  margin-top: 4px;
}

.foot {
  margin-top: 72px; padding-top: 16px;
  border-top: 1px solid var(--ink);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.1em;
  display: flex; justify-content: space-between;
  flex-wrap: wrap; gap: 16px;
}
"""


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title id="docTitle">Robo · Careers</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;0,9..144,900;1,9..144,400&family=JetBrains+Mono:wght@400;500;700&family=Noto+Serif+KR:wght@300;400;500;600;700;900&family=Pretendard:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>__CSS__</style>
</head>
<body>
<div class="grain"></div>
<div class="container">

  <header class="masthead">
    <div class="brand">Robo <span class="amp">·</span> Careers</div>
    <div class="meta">
      <div class="meta-row">
        Vol. 2<span class="dot">·</span>Robotics Series<span class="dot">·</span>n=<span id="nLabel">?</span><span class="dot">·</span><span id="builtLabel">built</span> __DATE__
      </div>
      <div class="meta-row">
        ICRA · IROS · RA-L · T-RO · RSS · IJRR · Sci-Rob
      </div>
      <div class="meta-row">
        <span id="sourceLabel">source:</span> <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank" rel="noopener">robopaper-atlas&nbsp;↗</a>
        <span class="lang-tabs">
          <a class="lang-tab" data-lang="en" href="#en">EN</a>
          <span class="lang-sep">/</span>
          <a class="lang-tab" data-lang="ko" href="#ko">KO</a>
        </span>
      </div>
    </div>
  </header>

  <section class="hero">
    <div>
      <span class="kicker" id="heroKicker"></span>
      <h1 id="heroHeadline"></h1>
    </div>
    <div class="hero-note" id="heroNote"></div>
  </section>

  <section>
    <h2><span id="secLessonsTitle"></span> <span class="sub" id="secLessonsSub"></span></h2>
    <p class="section-desc" id="secLessonsDesc"></p>
    <div class="cross-lessons"><ol id="crossLessons"></ol></div>
  </section>

  <section>
    <h2 id="rankTitle">Top</h2>
    <p class="section-desc" id="secTopDesc"></p>
    <table class="rank-table" id="rankTable">
      <thead>
        <tr>
          <th data-key="rank">#</th>
          <th data-key="name" style="text-align:left">Name</th>
          <th data-key="archetype" style="text-align:left">Archetype</th>
          <th data-key="papers">Papers</th>
          <th data-key="total_cites">Cites</th>
          <th data-key="h_index">h</th>
          <th data-key="seminal_count">500+</th>
          <th data-key="span">Span</th>
          <th data-key="first_year">First</th>
          <th data-key="last_year">Last</th>
          <th data-key="hub_degree">Hub</th>
          <th data-key="pivot">Pivot</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </section>

  <section>
    <h2><span id="secArcTitle"></span> <span class="sub" id="secArcSub"></span></h2>
    <p class="section-desc" id="secArcDesc"></p>
    <div class="archetype-grid" id="archetypeGrid"></div>
  </section>

  <section>
    <h2><span id="secTimingTitle"></span> <span class="sub" id="secTimingSub"></span></h2>
    <p class="section-desc" id="secTimingDesc"></p>
    <div class="timing-grid" id="timingGrid"></div>
  </section>

  <section>
    <h2><span id="secTopicsTitle"></span> <span class="sub" id="secTopicsSub"></span></h2>
    <p class="section-desc" id="secTopicsDesc"></p>
    <div class="topic-dom" id="topicDom"></div>
  </section>

  <section>
    <h2><span id="secProfilesTitle"></span> <span class="sub" id="secProfilesSub"></span></h2>
    <p class="section-desc" id="secProfilesDesc"></p>
    <div class="profile-filter">
      <input type="text" id="profileSearch" placeholder="" />
      <div class="filter-chips" id="archetypeChips"></div>
    </div>
    <div class="profile-grid" id="profileGrid"></div>
  </section>

  <footer class="foot">
    <span id="footData"></span>
    <span id="footTech"></span>
    <span id="footBuilt">Built __DATE__</span>
  </footer>
</div>

<script>
const META = __META__;
const PROFILES = __PROFILES__;

const I18N = {
  en: {
    docTitle: "Robo · Careers — trajectories of the masters",
    built: "built",
    source: "source:",
    heroKicker: n => `80,000+ papers · 40 years · ${n} trajectories`,
    heroHeadline: `Where do "master" careers <em>diverge</em>?`,
    heroNote: n => `Across 40 years of major robotics venues — a composite ranking of impact, persistence, hub centrality, blockbuster count, and career span produces the top ${n} below. Data: <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank" style="color:var(--accent);">robopaper-atlas</a> (DBLP + OpenAlex, 81,680 papers).`,
    secLessonsTitle: "Lessons",
    secLessonsSub: "/ WHAT THIS MEANS FOR YOU",
    secLessonsDesc: "Bottom line first. Patterns below are auto-extracted across all profiles.",
    rankTitle: n => `Top ${n}`,
    secTopDesc: "Composite = z-score sum of total cites, h-index, blockbusters (≥500 cites), career span, and hub degree. Click headers to sort.",
    secArcTitle: "Archetypes",
    secArcSub: "/ CAREER ARC TYPOLOGY",
    secArcDesc: "KMeans over normalized per-year citation curves. Each centroid is a 'shape of mastery'.",
    secTimingTitle: "Timing",
    secTimingSub: "/ WHEN DOES IT HAPPEN",
    secTimingDesc: "How many years after the first paper do key milestones land?",
    secTopicsTitle: "Topic dominance",
    secTopicsSub: "/ OVERLAPPING SUBJECTS",
    secTopicsDesc: "Weighted sum of OpenAlex concepts. Who contributed most substantively to each subject.",
    secProfilesTitle: "Profiles",
    secProfilesSub: "/ INDIVIDUAL TRAJECTORIES",
    secProfilesDesc: "Career sparkline · milestones · top coauthors · topic drift · auto-generated narrative. Filter by archetype or search.",
    searchPlaceholder: "Search by name...",
    peakPaper: "Peak paper",
    topicDrift: "Topic drift (early → recent)",
    pivotWord: "pivot",
    coauthors: "Top recurring coauthors",
    lineage: "Academic lineage",
    lineageNote: "(inferred from coauthor patterns)",
    blockbusters: "Top 3 blockbusters",
    careerLessons: "Career lessons",
    noMentor: "No mentor signal (self-started or sparse early data)",
    noStudent: "No student signal",
    moreStudents: n => `+ ${n} more`,
    studentMeta: s => `${s.student_first_year}~${s.last_copub_year} · we last-author on ${s.we_last_author_count} of ${s.student_first_author_count}`,
    advisorMeta: a => `${a.advisor_active_from}~ · last-author on ${a.advisor_last_author_count} of ${a.early_copubs_as_our_first_author} of our early 1st-author papers`,
    coauthMeta: c => `× ${c.count} · ${c.first_year}~${c.last_year}`,
    peakMeta: (y, c) => `${y} · ${c.toLocaleString()} cites`,
    timeLabels: {
      "years_to_first_100cite": "Years to first 100+ cite paper",
      "years_to_first_500cite": "Years to first 500+ cite paper",
      "years_to_first_1000cite": "Years to first 1000+ cite paper",
      "peak_paper_relative_position": "Peak position (career %)",
      "career_span_years": "Total career span",
    },
    timingUnit: "y",
    timingMedianSuffix: " (median)",
    timingRangeRender: d => `n=${d.n} · range ${d.min}–${d.max} · mean ${d.mean}`,
    footData: `Data: <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank" style="color:inherit;">robopaper-atlas</a> · DBLP + OpenAlex`,
    footTech: `Built with Chart.js · no external runtime data`,
  },
  ko: {
    docTitle: "Robo · Careers — 대가들의 궤적",
    built: "빌드",
    source: "출처:",
    heroKicker: n => `80,000+ 편 · 40년 · ${n}인의 궤적`,
    heroHeadline: `"대가"의 커리어는 어디서 <em>갈라지는가</em>.`,
    heroNote: n => `로보틱스 주요 venue 40년치 논문을 통틀어, 영향력·지속성·허브성·블록버스터 생산량·커리어 기간을 합산한 상위 ${n}인의 이력을 한 페이지에 풀었다. 데이터 출처: <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank" style="color:var(--accent);">robopaper-atlas</a> (DBLP + OpenAlex, 81,680편).`,
    secLessonsTitle: "교훈",
    secLessonsSub: "/ WHAT THIS MEANS FOR YOU",
    secLessonsDesc: "결론부터. 아래는 전체 프로필을 횡단해 자동 추출한 수치·패턴.",
    rankTitle: n => `Top ${n}`,
    secTopDesc: "합성 점수 = 총 인용 · h-index · 블록버스터(500+인용) 개수 · 커리어 기간 · 허브 연결도의 z-score 합. 헤더 클릭 정렬.",
    secArcTitle: "아키타입",
    secArcSub: "/ CAREER ARC TYPOLOGY",
    secArcDesc: "정규화된 연도별 인용 발생 곡선을 KMeans로 군집화. 각 센트로이드의 모양이 \"대가 커리어의 꼴\".",
    secTimingTitle: "타이밍",
    secTimingSub: "/ WHEN DOES IT HAPPEN",
    secTimingDesc: "첫 논문으로부터 몇 년 뒤에 각 마일스톤이 찍혔는가.",
    secTopicsTitle: "주제 지배도",
    secTopicsSub: "/ OVERLAPPING SUBJECTS",
    secTopicsDesc: "OpenAlex concepts 가중합. 어느 대가가 어느 주제에 얼마나 실체적으로 기여했는지.",
    secProfilesTitle: "프로필",
    secProfilesSub: "/ INDIVIDUAL TRAJECTORIES",
    secProfilesDesc: "커리어 스파크라인 · 마일스톤 · 상위 공저자 · 토픽 변천 · 자동 생성 서술. 아키타입 / 검색으로 필터.",
    searchPlaceholder: "이름 검색...",
    peakPaper: "Peak paper",
    topicDrift: "토픽 변천 (초기 → 최근)",
    pivotWord: "pivot",
    coauthors: "상위 반복 공저자",
    lineage: "Academic lineage",
    lineageNote: "(공저 패턴 추정)",
    blockbusters: "블록버스터 Top 3",
    careerLessons: "커리어 교훈",
    noMentor: "멘토 후보 신호 없음 (자체 시작 또는 데이터 부족)",
    noStudent: "제자 후보 신호 없음",
    moreStudents: n => `+ ${n}명 더`,
    studentMeta: s => `${s.student_first_year}~${s.last_copub_year} · 우리 마지막저자 ${s.we_last_author_count}편 / ${s.student_first_author_count}편 중`,
    advisorMeta: a => `${a.advisor_active_from}~ · 초기 1저자 ${a.early_copubs_as_our_first_author}편 중 마지막저자 ${a.advisor_last_author_count}편`,
    coauthMeta: c => `× ${c.count}회 · ${c.first_year}~${c.last_year}`,
    peakMeta: (y, c) => `${y} · ${c.toLocaleString()}회 인용`,
    timeLabels: {
      "years_to_first_100cite": "첫 100+ 인용까지",
      "years_to_first_500cite": "첫 500+ 인용까지",
      "years_to_first_1000cite": "첫 1000+ 인용까지",
      "peak_paper_relative_position": "최고점 위치 (커리어 %)",
      "career_span_years": "커리어 총 기간",
    },
    timingUnit: "년",
    timingMedianSuffix: " (중앙값)",
    timingRangeRender: d => `n=${d.n} · 범위 ${d.min}–${d.max} · 평균 ${d.mean}`,
    footData: `데이터: <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank" style="color:inherit;">robopaper-atlas</a> · DBLP + OpenAlex`,
    footTech: `Chart.js 사용 · 런타임 외부 데이터 없음`,
  }
};

let CHARTS = [];
function newChart(ctx, cfg) { const c = new Chart(ctx, cfg); CHARTS.push(c); return c; }
function destroyAllCharts() { while (CHARTS.length) { try { CHARTS.pop().destroy(); } catch(e) {} } }

function getLang() {
  const h = window.location.hash.replace('#','').toLowerCase();
  if (h === 'ko' || h === 'kor') return 'ko';
  return 'en';
}
let LANG = getLang();
let T = I18N[LANG];

function setLang(l) {
  LANG = l; T = I18N[l];
  // update URL hash
  if (l === 'en') history.replaceState(null, '', window.location.pathname + window.location.search);
  else history.replaceState(null, '', '#' + l);
  document.documentElement.lang = l === 'ko' ? 'ko' : 'en';
  renderAll();
}

function applyStaticI18n() {
  const n = PROFILES.length;
  document.getElementById('docTitle').textContent = T.docTitle;
  document.title = T.docTitle;
  document.getElementById('builtLabel').textContent = T.built;
  document.getElementById('sourceLabel').textContent = T.source;
  document.getElementById('nLabel').textContent = n;
  document.getElementById('heroKicker').textContent = T.heroKicker(n);
  document.getElementById('heroHeadline').innerHTML = T.heroHeadline;
  document.getElementById('heroNote').innerHTML = T.heroNote(n);
  document.getElementById('secLessonsTitle').textContent = T.secLessonsTitle;
  document.getElementById('secLessonsSub').textContent = T.secLessonsSub;
  document.getElementById('secLessonsDesc').textContent = T.secLessonsDesc;
  document.getElementById('rankTitle').textContent = T.rankTitle(n);
  document.getElementById('secTopDesc').textContent = T.secTopDesc;
  document.getElementById('secArcTitle').textContent = T.secArcTitle;
  document.getElementById('secArcSub').textContent = T.secArcSub;
  document.getElementById('secArcDesc').textContent = T.secArcDesc;
  document.getElementById('secTimingTitle').textContent = T.secTimingTitle;
  document.getElementById('secTimingSub').textContent = T.secTimingSub;
  document.getElementById('secTimingDesc').textContent = T.secTimingDesc;
  document.getElementById('secTopicsTitle').textContent = T.secTopicsTitle;
  document.getElementById('secTopicsSub').textContent = T.secTopicsSub;
  document.getElementById('secTopicsDesc').textContent = T.secTopicsDesc;
  document.getElementById('secProfilesTitle').textContent = T.secProfilesTitle;
  document.getElementById('secProfilesSub').textContent = T.secProfilesSub;
  document.getElementById('secProfilesDesc').textContent = T.secProfilesDesc;
  document.getElementById('profileSearch').placeholder = T.searchPlaceholder;
  document.getElementById('footData').innerHTML = T.footData;
  document.getElementById('footTech').textContent = T.footTech;
  document.querySelectorAll('.lang-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.lang === LANG);
  });
}

/* === Top table === */
function renderTable() {
  const tbody = document.querySelector('#rankTable tbody');
  const rows = PROFILES.map(p => ({
    rank: p._rank_info.rank,
    slug: p.slug,
    name: p.name,
    archetype: (p.insights && p.insights[LANG]?.archetype) || '—',
    papers: p.career_stats.total_papers,
    total_cites: p.career_stats.total_cites,
    h_index: p.career_stats.h_index,
    seminal_count: p.career_stats.seminal_count,
    span: p.career_stats.span,
    first_year: p.career_stats.first_year,
    last_year: p.career_stats.last_year,
    hub_degree: p._rank_info.hub_degree || 0,
    pivot: p.pivot_score,
  }));
  let sortKey = 'rank', sortDir = 1;
  function paint() {
    const sorted = [...rows].sort((a,b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av < bv) return -1*sortDir;
      if (av > bv) return 1*sortDir;
      return 0;
    });
    tbody.innerHTML = sorted.map(r => `
      <tr>
        <td class="rank">${r.rank}</td>
        <td class="name"><a href="#p-${r.slug}" style="color:inherit; text-decoration:none; border-bottom:1px dotted currentColor;">${r.name}</a></td>
        <td class="archetype">${r.archetype}</td>
        <td>${r.papers}</td>
        <td>${r.total_cites.toLocaleString()}</td>
        <td>${r.h_index}</td>
        <td>${r.seminal_count}</td>
        <td>${r.span}</td>
        <td>${r.first_year}</td>
        <td>${r.last_year}</td>
        <td>${r.hub_degree}</td>
        <td>${r.pivot.toFixed(2)}</td>
      </tr>`).join('');
    document.querySelectorAll('#rankTable th').forEach(th => {
      th.classList.remove('sort-asc','sort-desc');
      if (th.dataset.key === sortKey) {
        th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
      }
    });
  }
  document.querySelectorAll('#rankTable th').forEach(th => {
    th.onclick = () => {
      const k = th.dataset.key;
      if (k === sortKey) sortDir = -sortDir;
      else { sortKey = k; sortDir = (k === 'rank' || k === 'name' || k === 'archetype' || k === 'first_year') ? 1 : -1; }
      paint();
    };
  });
  paint();
}

/* === Archetypes === */
function renderArchetypes() {
  const grid = document.getElementById('archetypeGrid');
  grid.innerHTML = META.archetypes.map((a, i) => `
    <div class="archetype-card">
      <h3>${a.label}</h3>
      <div class="chart-box"><canvas id="arc-${i}"></canvas></div>
      <div class="members"><strong>${a.members.length}</strong>: ${a.members.join(', ')}</div>
    </div>`).join('');
  META.archetypes.forEach((a, i) => {
    const ctx = document.getElementById(`arc-${i}`);
    newChart(ctx, {
      type: 'line',
      data: {
        labels: a.centroid.map((_,j) => j),
        datasets: [{
          data: a.centroid,
          borderColor: '#c1440e',
          backgroundColor: 'rgba(193,68,14,0.15)',
          fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
      }
    });
  });
}

/* === Timing === */
function renderTiming() {
  const grid = document.getElementById('timingGrid');
  const ordered = [
    'years_to_first_100cite','years_to_first_500cite','years_to_first_1000cite',
    'peak_paper_relative_position','career_span_years'
  ];
  const items = ordered.map(k => [k, T.timeLabels[k], META.timing_distributions[k]]).filter(x => x[2]);
  grid.innerHTML = items.map(([key, label, d], i) => {
    const isPct = key === 'peak_paper_relative_position';
    const unit = isPct ? '' : T.timingUnit;
    const medDisp = isPct ? `${(d.median * 100).toFixed(0)}%` : `${d.median}`;
    const rangeStr = (isPct
      ? `n=${d.n} · ${(d.min*100).toFixed(0)}%–${(d.max*100).toFixed(0)}% · mean ${(d.mean*100).toFixed(0)}%`
      : T.timingRangeRender(d));
    const suffix = isPct ? T.timingMedianSuffix : ` ${unit}${T.timingMedianSuffix}`;
    return `
      <div class="timing-card">
        <div class="label">${label}</div>
        <div class="value">${medDisp}<span class="unit">${suffix}</span></div>
        <div class="range">${rangeStr}</div>
        <div class="chart-box"><canvas id="ti-${i}"></canvas></div>
      </div>`;
  }).join('');
  items.forEach(([key, label, d], i) => {
    const isPct = key === 'peak_paper_relative_position';
    const ctx = document.getElementById(`ti-${i}`);
    const vals = d.values.slice();
    const nB = Math.min(10, Math.max(4, Math.ceil(Math.sqrt(vals.length))));
    const step = (d.max - d.min) / nB || 1;
    const buckets = new Array(nB).fill(0);
    const labels = [];
    for (let b = 0; b < nB; b++) {
      const lo = d.min + b*step;
      const hi = d.min + (b+1)*step;
      labels.push(isPct ? `${(lo*100).toFixed(0)}` : `${lo.toFixed(0)}`);
      buckets[b] = vals.filter(v => (b === nB-1 ? (v >= lo && v <= hi) : (v >= lo && v < hi))).length;
    }
    newChart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ data: buckets, backgroundColor: '#2d4a3e', borderRadius: 2 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { font: { size: 9 }, color: '#6b6259' }, grid: { display: false } },
          y: { display: false, beginAtZero: true },
        },
      }
    });
  });
}

/* === Topic dominance === */
function renderTopics() {
  const grid = document.getElementById('topicDom');
  grid.innerHTML = META.topic_dominance.slice(0, 12).map(t => `
    <div class="t">
      <div class="c">${t.concept}</div>
      <div class="who">${t.top_contributors.map(c => c.name).join(' · ')}</div>
    </div>`).join('');
}

/* === Profile cards === */
function renderProfiles() {
  const grid = document.getElementById('profileGrid');
  grid.innerHTML = PROFILES.map(p => {
    const cs = p.career_stats;
    const ms = p.milestones;
    const ri = p._rank_info || {};
    const ins = p.insights?.[LANG] || {};
    const arc = ins.archetype || '—';
    const firstCW = p.topic_windows?.[0];
    const lastCW = p.topic_windows?.[p.topic_windows.length - 1];
    const firstTopics = firstCW ? firstCW.top_concepts.map(t => `<span class="tag">${t.c}</span>`).join('') : '';
    const lastTopics = lastCW ? lastCW.top_concepts.map(t => `<span class="tag">${t.c}</span>`).join('') : '';
    const coauth = (p.top_repeat_coauthors || []).slice(0,5)
      .map(c => `<li>${c.name} <span style="color:var(--muted)">${T.coauthMeta(c)}</span></li>`).join('');
    const advs = (p.likely_advisors || []).slice(0,3)
      .map(a => `<li>🎓 <strong>${a.name}</strong> <span style="color:var(--muted)">${T.advisorMeta(a)}</span></li>`).join('');
    const studs = (p.likely_students || []).slice(0,6)
      .map(s => `<li>👥 <strong>${s.name}</strong> <span style="color:var(--muted)">${T.studentMeta(s)}</span></li>`).join('');
    const studCount = (p.likely_students || []).length;
    const blocks = (p.blockbusters || []).slice(0,3)
      .map(b => `<li>${b.year} <strong>${b.cites.toLocaleString()}</strong>c · <em>${b.title}</em></li>`).join('');
    const lessons = (ins.lessons || []).map(l => `<li>${l}</li>`).join('');
    const paras = (ins.paragraphs || []).filter(x => x).map(x => `<p>${x}</p>`).join('');
    return `
      <article class="profile-card" id="p-${p.slug}" data-name="${p.name}" data-arc="${arc}">
        <div class="profile-head">
          <div class="rank-badge">#${ri.rank || '?'} · composite ${(ri.composite||0).toFixed(2)}</div>
          <h3>${p.name}</h3>
          <span class="archetype-tag">${arc}</span>
        </div>
        <div class="profile-stats">
          <div class="stat"><div class="k">papers</div><div class="v">${cs.total_papers}</div></div>
          <div class="stat"><div class="k">cites</div><div class="v">${cs.total_cites.toLocaleString()}</div></div>
          <div class="stat"><div class="k">h-idx</div><div class="v">${cs.h_index}</div></div>
          <div class="stat"><div class="k">span</div><div class="v">${cs.span}y</div></div>
        </div>
        <div class="spark-box"><canvas id="sp-${p.slug}"></canvas></div>
        <div class="profile-section">
          <h4>${T.peakPaper}</h4>
          <div class="peak">
            <em>${ms.peak_paper?.title || '—'}</em>
            <div class="meta">${T.peakMeta(ms.peak_paper?.year || '', ms.peak_paper?.cites || 0)}</div>
          </div>
        </div>
        <div class="profile-section">
          <h4>${T.topicDrift}</h4>
          <div style="margin-bottom:6px;">${firstTopics || '<span style="color:var(--muted)">—</span>'}</div>
          <div style="color:var(--muted); font-size:0.75rem;">⇣ ${T.pivotWord} ${p.pivot_score?.toFixed(2) || '0.00'}</div>
          <div style="margin-top:6px;">${lastTopics || '<span style="color:var(--muted)">—</span>'}</div>
        </div>
        <div class="profile-section">
          <h4>${T.coauthors}</h4>
          <ul>${coauth}</ul>
        </div>
        <div class="profile-section">
          <h4>${T.lineage} <span class="soft">${T.lineageNote}</span></h4>
          ${advs ? `<ul>${advs}</ul>` : `<div style="color:var(--muted); font-size:0.78rem;">${T.noMentor}</div>`}
          ${studs ? `<ul style="margin-top:6px;">${studs}</ul>${studCount > 6 ? `<div style="color:var(--muted); font-size:0.75rem; margin-top:4px;">${T.moreStudents(studCount - 6)}</div>` : ''}` : `<div style="color:var(--muted); font-size:0.78rem; margin-top:6px;">${T.noStudent}</div>`}
        </div>
        <div class="profile-section">
          <h4>${T.blockbusters}</h4>
          <ul>${blocks}</ul>
        </div>
        <div class="narrative">${paras}</div>
        <div class="lessons">
          <h4>${T.careerLessons}</h4>
          <ul>${lessons}</ul>
        </div>
      </article>`;
  }).join('');

  PROFILES.forEach(p => {
    const ctx = document.getElementById(`sp-${p.slug}`);
    const ys = p.year_series;
    const years = Object.keys(ys).map(Number).sort((a,b) => a-b);
    const papers = years.map(y => ys[y].n);
    const cites = years.map(y => ys[y].cites);
    newChart(ctx, {
      type: 'line',
      data: {
        labels: years,
        datasets: [
          { label: 'papers/yr', data: papers, borderColor: '#2d4a3e', backgroundColor: 'rgba(45,74,62,0.15)', fill: true, tension: 0.25, pointRadius: 0, borderWidth: 1.5, yAxisID: 'y' },
          { label: 'cites/yr',  data: cites,  borderColor: '#c1440e', backgroundColor: 'transparent', fill: false, tension: 0.25, pointRadius: 0, borderWidth: 1.5, yAxisID: 'y2' },
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { font: { size: 8 }, color: '#6b6259', maxTicksLimit: 6 }, grid: { display: false } },
          y:  { display: false, beginAtZero: true },
          y2: { display: false, beginAtZero: true, position: 'right' },
        },
      }
    });
  });
}

/* === Filter === */
function renderFilter() {
  const chips = document.getElementById('archetypeChips');
  const archetypes = ['ALL', ...new Set(PROFILES.map(p => p.insights?.[LANG]?.archetype).filter(Boolean))];
  chips.innerHTML = archetypes.map(a =>
    `<span class="chip ${a === 'ALL' ? 'active' : ''}" data-arc="${a}">${a}</span>`
  ).join('');
  const input = document.getElementById('profileSearch');
  let activeArc = 'ALL';
  function apply() {
    const q = input.value.trim().toLowerCase();
    document.querySelectorAll('.profile-card').forEach(card => {
      const name = (card.dataset.name || '').toLowerCase();
      const arc = card.dataset.arc || '';
      const matchQ = !q || name.includes(q);
      const matchA = activeArc === 'ALL' || arc === activeArc;
      card.classList.toggle('hidden', !(matchQ && matchA));
    });
  }
  chips.onclick = (e) => {
    const t = e.target.closest('.chip');
    if (!t) return;
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    t.classList.add('active');
    activeArc = t.dataset.arc;
    apply();
  };
  input.oninput = apply;
}

/* === Cross lessons === */
function mdBold(s) { return (s || '').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>'); }
function renderCross() {
  const ol = document.getElementById('crossLessons');
  const items = (META.cross_lessons && META.cross_lessons[LANG]) || [];
  ol.innerHTML = items.map(l => `<li>${mdBold(l)}</li>`).join('');
}

function renderAll() {
  destroyAllCharts();
  applyStaticI18n();
  renderTable();
  renderArchetypes();
  renderTiming();
  renderTopics();
  renderProfiles();
  renderFilter();
  renderCross();
}

/* Lang tabs */
document.querySelectorAll('.lang-tab').forEach(t => {
  t.addEventListener('click', (e) => {
    e.preventDefault();
    setLang(t.dataset.lang);
  });
});
window.addEventListener('hashchange', () => {
  const l = getLang();
  if (l !== LANG) { LANG = l; T = I18N[l]; renderAll(); }
});

renderAll();
</script>
</body>
</html>
"""


def main():
    meta, profiles = load_all()
    html = (
        HTML_TEMPLATE
        .replace("__CSS__", CSS)
        .replace("__META__", json.dumps(meta, ensure_ascii=False))
        .replace("__PROFILES__", json.dumps(profiles, ensure_ascii=False))
        .replace("__DATE__", datetime.date.today().isoformat())
    )
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"Wrote {OUT_PATH} ({size_kb:.1f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
