"""Phase 6: build authors/<slug>.html — rich per-researcher pages.

One HTML per profile in `authors/`. Follows the researcher_profiles_ko_v2.html
aesthetic (hero + facts + phases + themes + pullquote + highlights + lineage).
Bilingual (EN default, KO via URL hash #ko).
"""
from __future__ import annotations

import collections
import datetime
import glob
import hashlib
import json
import os
import statistics
import sys


def _pick(variants, seed: str):
    """Deterministic selection — same seed always gets the same variant."""
    if not variants:
        return ""
    h = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)
    return variants[h % len(variants)]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.io import build_author_index, load_papers
from common.phrases import build_global_idf, distinctive_phrases, prettify
from common.glossary import lookup_phrases as lookup_glossary

META_PATH = "analysis/meta.json"
PROFILES_DIR = "analysis/profiles"
OUT_DIR = "authors"
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

# -----------------------------------------------------------------------------
# Data loading & helpers
# -----------------------------------------------------------------------------

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
    return meta, profiles


def blockbusters_in_window(profile, start, end):
    return [p for p in profile.get("blockbusters", []) if start <= p["year"] <= end]


def papers_in_window(author_papers, start, end):
    return [p for p in author_papers if p.get("year") and start <= p["year"] <= end]


def phrases_for_window(author_papers, start, end, idf, max_idf, k=5):
    win = papers_in_window(author_papers, start, end)
    phrases = distinctive_phrases(win, idf, max_idf, top_k=k)
    return [prettify(p) for p in phrases]


def phrases_for_span(author_papers, idf, max_idf, k=5):
    phrases = distinctive_phrases(author_papers, idf, max_idf, top_k=k)
    return [prettify(p) for p in phrases]


def students_starting_in(profile, start, end):
    return [s for s in profile.get("likely_students", []) if start <= s["student_first_year"] <= end]


def top_coauthors_in_window(collab_window, exclude=None):
    exclude = exclude or set()
    tops = collab_window.get("top_coauthors", [])
    out = [(n, c) for n, c in tops if n not in exclude]
    return out


def dominant_venue(venue_window):
    mix = venue_window.get("mix", {})
    if not mix:
        return None, 0.0
    total = sum(mix.values()) or 1
    top = max(mix.items(), key=lambda x: x[1])
    return top[0], top[1] / total


def concept_continuity(profile, top_k_per_window=3, ignore=None):
    ignore = set(ignore or []) | {"Computer science", "Artificial intelligence"}
    windows = profile.get("topic_windows", [])
    if not windows:
        return []
    hits = collections.Counter()
    for w in windows:
        for t in w["top_concepts"][:top_k_per_window]:
            if t["c"] not in ignore:
                hits[t["c"]] += 1
    threshold = max(2, int(len(windows) * 0.55))
    return [c for c, n in hits.most_common() if n >= threshold]


def first_last_concepts(profile, k=2):
    ws = profile.get("topic_windows", [])
    if not ws:
        return [], []
    early = [t["c"] for t in ws[0]["top_concepts"][:k] if t["c"] not in ("Computer science",)]
    late = [t["c"] for t in ws[-1]["top_concepts"][:k] if t["c"] not in ("Computer science",)]
    return early or [t["c"] for t in ws[0]["top_concepts"][:k]], late or [t["c"] for t in ws[-1]["top_concepts"][:k]]


def format_paper_title(title, max_len=85):
    if not title:
        return ""
    if len(title) <= max_len:
        return title
    return title[: max_len - 1].rstrip() + "…"


# -----------------------------------------------------------------------------
# Narrative generators — return structured dicts per lang
# -----------------------------------------------------------------------------

def tagline(profile, lang, author_papers, idf, max_idf):
    windows = profile.get("topic_windows", [])
    if not windows:
        return ""
    parts = []
    # first
    ws = windows[0]
    first_phr = phrases_for_window(author_papers, ws["start"], ws["end"], idf, max_idf, k=2)
    if first_phr:
        parts.append(first_phr[0])
    # middle (two-thirds in)
    if len(windows) >= 3:
        mid = windows[len(windows) * 2 // 3 - 1]
        mid_phr = phrases_for_window(author_papers, mid["start"], mid["end"], idf, max_idf, k=2)
        if mid_phr and mid_phr[0] not in parts:
            parts.append(mid_phr[0])
    # last
    wl = windows[-1]
    last_phr = phrases_for_window(author_papers, wl["start"], wl["end"], idf, max_idf, k=2)
    if last_phr and last_phr[0] not in parts:
        parts.append(last_phr[0])
    if not parts:
        # fallback
        early, late = first_last_concepts(profile, k=1)
        parts = (early or []) + (late or [])
    return " → ".join(parts[:3])


def one_liner(profile, lang, author_papers, idf, max_idf):
    cs = profile["career_stats"]
    pivot = profile.get("pivot_score", 0)
    students = profile.get("likely_students", [])
    bbs = profile.get("blockbusters", [])
    top_bb = bbs[0] if bbs else None
    # distinctive phrases: early / late / career-long anchor
    windows = profile.get("topic_windows", [])
    early = []
    late = []
    if windows:
        early = phrases_for_window(author_papers, windows[0]["start"], windows[0]["end"], idf, max_idf, k=2)
        late = phrases_for_window(author_papers, windows[-1]["start"], windows[-1]["end"], idf, max_idf, k=2)
    career_phrases = phrases_for_span(author_papers, idf, max_idf, k=5)
    anchor_phrase = career_phrases[0] if career_phrases else ""

    early_s = early[0] if early else ""
    late_s = late[0] if late else ""

    if lang == "ko":
        bits = [f"{cs['first_year']}년에 출판을 시작해 {cs['span']}년째 현장에 머물고 있는 연구자."]
        if pivot >= 0.4 and early_s and late_s and early_s != late_s:
            bits.append(
                f"그의 궤적은 <em>{early_s}</em>에서 <em>{late_s}</em>에 이르는 긴 재창조의 연쇄였다 — "
                "같은 이름으로 서명했지만 실제로 다뤘던 질문은 10년에 한 번씩 크게 갈아엎혔다."
            )
        elif pivot < 0.2 and cs["total_papers"] >= 150 and anchor_phrase:
            bits.append(
                f"주제를 크게 옮긴 적이 없다. <em>{anchor_phrase}</em>라는 축 하나를 {cs['span']}년 내내 파고든 결과가 "
                f"{cs['total_papers']}편, h={cs['h_index']}이라는 숫자다."
            )
        elif early_s and late_s and early_s != late_s:
            bits.append(
                f"초기에는 <em>{early_s}</em>를 다루었고, 최근에는 <em>{late_s}</em>가 중심으로 올라왔다. "
                "급격한 단절이라기보다는 인접 영역을 꾸준히 밀고 나간 점진적 확장에 가깝다."
            )
        elif anchor_phrase:
            bits.append(f"<em>{anchor_phrase}</em>를 평생의 중심축으로 삼고 꾸준히 깊이를 더해온 유형.")
        if top_bb and top_bb.get("cites", 0) >= 500:
            bits.append(
                f"대표작은 {top_bb['year']}년 {top_bb['venue']}에 실린 \"{format_paper_title(top_bb['title'], 70)}\" "
                f"({top_bb['cites']:,}회 인용)."
            )
        if len(students) >= 20:
            bits.append(
                f"공저 패턴으로 추정되는 제자만 {len(students)}명 — "
                "이 정도 규모에 이르면 개인 생산자가 아니라 학파를 운영하는 그룹 리더로 읽어야 한다."
            )
        elif len(students) >= 8:
            bits.append(
                f"이 시기 {len(students)}명의 후배가 그의 곁에서 커리어를 시작했다는 신호가 포착된다."
            )
        return " ".join(bits)
    else:
        bits = [f"Began publishing in {cs['first_year']} and is still active {cs['span']} years on."]
        if pivot >= 0.4 and early_s and late_s and early_s != late_s:
            bits.append(
                f"The trajectory runs from <em>{early_s}</em> to <em>{late_s}</em> — a chain of reinventions. "
                "The same name stayed on the papers, but the actual question got rewritten every decade or so."
            )
        elif pivot < 0.2 and cs["total_papers"] >= 150 and anchor_phrase:
            bits.append(
                f"Rarely changed lane. <em>{anchor_phrase}</em> for {cs['span']} straight years — "
                f"the ledger shows {cs['total_papers']} papers and an h-index of {cs['h_index']}."
            )
        elif early_s and late_s and early_s != late_s:
            bits.append(
                f"Early work sat in <em>{early_s}</em>; recent work centers on <em>{late_s}</em>. "
                "More of an incremental broadening than a sharp pivot."
            )
        elif anchor_phrase:
            bits.append(f"Anchored to <em>{anchor_phrase}</em> throughout, steadily deepening.")
        if top_bb and top_bb.get("cites", 0) >= 500:
            bits.append(
                f"The landmark is the {top_bb['year']} {top_bb['venue']} paper "
                f"\"{format_paper_title(top_bb['title'], 70)}\" ({top_bb['cites']:,} cites)."
            )
        if len(students) >= 20:
            bits.append(
                f"The coauthor signal suggests {len(students)} likely students — "
                "at this scale, read them as a group leader running a school, not a solo producer."
            )
        elif len(students) >= 8:
            bits.append(
                f"{len(students)} likely junior coauthors began their careers around them."
            )
        return " ".join(bits)


def build_facts(profile, author_papers, idf, max_idf, meta_archetype_map, lang):
    cs = profile["career_stats"]
    pivot = profile.get("pivot_score", 0)
    arc = meta_archetype_map.get(profile["name"], "—")
    top_bb = (profile.get("blockbusters") or [None])[0]

    career_phrases = phrases_for_span(author_papers, idf, max_idf, k=5)
    windows = profile.get("topic_windows", [])
    early_phr = phrases_for_window(author_papers, windows[0]["start"], windows[0]["end"], idf, max_idf, k=2) if windows else []
    late_phr = phrases_for_window(author_papers, windows[-1]["start"], windows[-1]["end"], idf, max_idf, k=2) if windows else []

    core_val = ", ".join(career_phrases[:2]) if career_phrases else "—"
    anchor = career_phrases[0] if career_phrases else "—"

    style_parts = [arc]
    if pivot >= 0.4:
        style_parts.append("pivoter")
    elif pivot < 0.2:
        style_parts.append("specialist")
    style = " · ".join(style_parts)

    if early_phr and late_phr and early_phr[0] != late_phr[0]:
        shift = f"{early_phr[0]} → {late_phr[0]}"
    else:
        shift = f"{anchor} (꾸준)" if lang == "ko" else f"{anchor} (steady)"

    if lang == "ko":
        rows = [
            ["시기",    f"<strong>{cs['first_year']} — {cs['last_year']}</strong>"],
            ["논문 수", f"{cs['total_papers']}편 · 인용 {cs['total_cites']:,} · h={cs['h_index']}"],
            ["핵심",    core_val],
            ["대표작",  format_paper_title(top_bb["title"], 48) if top_bb else "—"],
            ["스타일",  style],
            ["전환",    shift],
        ]
    else:
        rows = [
            ["Period",    f"<strong>{cs['first_year']} — {cs['last_year']}</strong>"],
            ["Papers",    f"{cs['total_papers']} · {cs['total_cites']:,} cites · h={cs['h_index']}"],
            ["Core",      core_val],
            ["Landmark",  format_paper_title(top_bb["title"], 48) if top_bb else "—"],
            ["Style",     style],
            ["Shift",     shift],
        ]
    return rows


def phase_title(win, win_phrases, idx, total, lang):
    """win_phrases: prettified distinctive phrases for this window (top N)."""
    core_phrases = win_phrases[:2] if win_phrases else []
    if not core_phrases:
        concepts = [t["c"] for t in win["top_concepts"] if t["c"] != "Computer science"][:2]
        core_phrases = concepts or [t["c"] for t in win["top_concepts"][:2]]
    if not core_phrases:
        return "—"
    core = " · ".join(core_phrases)
    if lang == "ko":
        if idx == 0:
            return f"출발점 — {core}"
        if idx == total - 1:
            return f"최근의 지형 — {core}"
        if idx == 1:
            return f"궤도의 안착 — {core}"
        if idx == total - 2:
            return f"성숙기의 확장 — {core}"
        return f"{core}의 시기"
    else:
        if idx == 0:
            return f"Opening bet — {core}"
        if idx == total - 1:
            return f"Latest terrain — {core}"
        if idx == 1:
            return f"Finding the orbit — {core}"
        if idx == total - 2:
            return f"Mature expansion — {core}"
        return f"Era of {core}"


# Variety pools for Korean prose — cycle by index to avoid monotony.
_KO_OPENERS = [
    "{ys}년부터 {ye}년 사이의 5년간,",
    "이어진 {ys}년대 전반, {ys}–{ye}년의 기간 동안",
    "그 뒤 {ys}년부터 {ye}년까지,",
    "{ys}년 무렵부터 {ye}년에 걸쳐,",
    "{ys}–{ye}년으로 이어진 이 시기에,",
    "{ys}년을 기점으로 {ye}년까지의 흐름 속에서,",
]
_EN_OPENERS = [
    "Between {ys} and {ye},",
    "Across the {ys}–{ye} stretch,",
    "Over the five years from {ys} to {ye},",
    "Then, from {ys} through {ye},",
    "In the {ys}–{ye} window,",
    "The {ys}–{ye} years saw",
]

def phase_body(profile, win, venue_win, collab_win, win_phrases, idx, total, lang):
    ys, ye = win["start"], win["end"]
    n = win["n_papers"]
    # Prefer distinctive phrases; fall back to concepts if window is too thin.
    if win_phrases:
        top_concepts = win_phrases[:3]
    else:
        top_concepts = [t["c"] for t in win["top_concepts"][:3] if t["c"] != "Computer science"][:3]
        if not top_concepts:
            top_concepts = [t["c"] for t in win["top_concepts"][:3]]
    bbs_here = blockbusters_in_window(profile, ys, ye)
    bbs_here = sorted(bbs_here, key=lambda p: -p["cites"])[:2]
    coauths = top_coauthors_in_window(collab_win)[:3]
    new_students = students_starting_in(profile, ys, ye)
    dom_venue, dom_share = dominant_venue(venue_win)
    family = profile["name"].split()[-1] if profile["name"] else ""

    seed_base = f"{profile['name']}::{idx}"

    if lang == "ko":
        opener = _KO_OPENERS[idx % len(_KO_OPENERS)].format(ys=ys, ye=ye)
        sents = []

        # Productivity
        if n >= 60:
            sents.append(_pick([
                f"{opener} 출판량이 눈에 띄게 불어난다 — 이 기간에만 <strong>{n}편</strong>이 쏟아진다.",
                f"{opener} 이 5년은 다작의 정점이다. 총 <strong>{n}편</strong>이 쌓인다.",
                f"{opener} 출판 강도가 확연히 높아진다. <strong>{n}편</strong>이 이 기간의 성과물이다.",
                f"{opener} 생산량이 피크를 찍는다. <strong>{n}편</strong>이 이 시기에 집중된다.",
            ], seed_base + "::prod"))
        elif n >= 30:
            sents.append(_pick([
                f"{opener} 총 <strong>{n}편</strong>의 논문이 나온다.",
                f"{opener} <strong>{n}편</strong>이 이 5년의 궤적에 올라간다.",
                f"{opener} 한창 활동기다 — <strong>{n}편</strong>이 기록된다.",
                f"{opener} <strong>{n}편</strong>을 남긴다.",
            ], seed_base + "::prod"))
        elif n >= 10:
            sents.append(_pick([
                f"{opener} <strong>{n}편</strong>이 이 기간의 출력물로 남는다.",
                f"{opener} 이 5년은 <strong>{n}편</strong>으로 기록된다.",
                f"{opener} 꾸준한 {n}편이다 — 과하지도 부족하지도 않은 리듬.",
                f"{opener} <strong>{n}편</strong>이 이 기간에 완성된다.",
            ], seed_base + "::prod"))
        else:
            sents.append(_pick([
                f"{opener} 이 구간은 {n}편으로 비교적 조용하다.",
                f"{opener} {n}편만이 이 시기의 출판물로 남는다.",
                f"{opener} 출판은 {n}편에 그친다 — 축적기에 가깝다.",
                f"{opener} {n}편 — 다음 국면을 준비하는 성격이 강하다.",
                f"{opener} {n}편이라는 적은 수 — 집중은 다른 곳에 있었던 듯한 시기.",
            ], seed_base + "::prod"))

        # Topic
        if top_concepts:
            tc_str = ", ".join(f"<span class='hl'>{c}</span>" for c in top_concepts[:2])
            sents.append(_pick([
                f"연구의 무게 중심은 {tc_str} 위에 놓여 있었고, 이 축은 이 시기 대부분의 성과물을 관통한다.",
                f"이 시기 연구는 {tc_str}을 중심으로 전개되었다.",
                f"주된 연구축은 {tc_str}에 있었다.",
                f"이 기간 작업의 골조는 {tc_str}에 놓인다.",
                f"{tc_str} — 이 시기 그의 출판물을 묶는 주된 틀이다.",
            ], seed_base + "::topic"))
            if len(top_concepts) > 2:
                sents.append(_pick([
                    f"거기에 {top_concepts[2]}가 보조 줄기로 올라온다.",
                    f"{top_concepts[2]} 또한 인접 줄기로 관찰된다.",
                    f"{top_concepts[2]}가 옆에서 병렬로 진행된다.",
                ], seed_base + "::topic2"))

        # Blockbusters
        if bbs_here:
            hit = bbs_here[0]
            sents.append(_pick([
                f"이 기간의 얼굴이 된 논문은 <em>\"{format_paper_title(hit['title'], 90)}\"</em>이다. "
                f"{hit['venue']} {hit['year']}에 실린 이 글은 지금까지 {hit['cites']:,}회 인용되며 이 분야의 표준 참조로 자리 잡았다.",
                f"이 시기의 앵커 페이퍼는 <em>\"{format_paper_title(hit['title'], 90)}\"</em>이다. "
                f"{hit['venue']} {hit['year']}, 누적 {hit['cites']:,}회 인용.",
                f"{hit['venue']} {hit['year']}의 <em>\"{format_paper_title(hit['title'], 90)}\"</em>이 이 시기를 대표한다 — "
                f"{hit['cites']:,}회 인용된 작업이다.",
            ], seed_base + "::bb1"))
            if len(bbs_here) > 1 and bbs_here[1]["cites"] >= 100:
                h2 = bbs_here[1]
                sents.append(_pick([
                    f"그 뒤를 잇는 것이 {h2['year']} {h2['venue']}의 <em>\"{format_paper_title(h2['title'], 75)}\"</em>({h2['cites']:,}회)이다.",
                    f"두 번째 앵커는 <em>\"{format_paper_title(h2['title'], 75)}\"</em>({h2['venue']} {h2['year']}, {h2['cites']:,}회).",
                    f"나란히 놓이는 것이 {h2['year']} {h2['venue']}의 <em>\"{format_paper_title(h2['title'], 75)}\"</em>({h2['cites']:,}회)이다.",
                ], seed_base + "::bb2"))
        elif n >= 20:
            sents.append(_pick([
                "이 기간에는 뚜렷한 단일 블록버스터보다는 꾸준한 중간층 생산으로 누적 인용이 쌓여간다.",
                "눈에 띄는 초대형 논문은 없다 — 대신 중간층의 논문들이 차곡차곡 쌓여 누적을 만든다.",
                "단 한 편에 의존하지 않는 시기다. 여러 중량급 논문이 분산되어 인용을 채운다.",
            ], seed_base + "::nobb"))

        # Coauthors
        if coauths:
            names = ", ".join(f"<strong>{n_}</strong>" for n_, c in coauths)
            if len(coauths) == 1:
                sents.append(_pick([
                    f"이 시기를 실질적으로 함께 끌고 간 파트너는 {names}이다.",
                    f"주된 공동 연구자는 {names}였다.",
                    f"이 시기 일의 대부분은 {names}와의 협업에서 나온다.",
                ], seed_base + "::co"))
            else:
                sents.append(_pick([
                    f"이 시기를 함께 끌어간 축은 {names}으로 요약된다.",
                    f"이 기간의 핵심 협력자: {names}.",
                    f"주된 공동 연구축은 {names}에 있다.",
                    f"이 시기의 실질적 작업 축은 {names}와의 협업이었다.",
                ], seed_base + "::co"))

        # Students
        if new_students:
            names = ", ".join(s["name"] for s in new_students[:4])
            more = f" 외 {len(new_students) - 4}명" if len(new_students) > 4 else ""
            sents.append(_pick([
                f"바로 이 시기에 {family}의 지도 아래에서 첫 논문을 낸 것으로 보이는 후배 연구자들이 나타난다 — {names}{more}. 개인 연구에서 그룹 운영으로의 전환이 이 시기 안에서 관찰된다.",
                f"{family}와 처음 공저를 시작한 후배 연구자들이 이 시기에 등장한다 — {names}{more}. 랩 규모가 본격적으로 커지는 신호다.",
                f"이 기간에 새로 합류한 후배로 {names}{more}이 보인다. {family} 연구실의 다음 세대가 이 시기에 형성된다.",
            ], seed_base + "::stu"))

        # Venue
        if dom_venue and dom_share >= 0.55:
            sents.append(_pick([
                f"발표 무대는 압도적으로 <span class='hl'>{dom_venue}</span>에 쏠려 있었다 — 이 시기 출판의 {dom_share:.0%}가 이 venue에서 소화되었다.",
                f"이 시기 출판물의 {dom_share:.0%}가 <span class='hl'>{dom_venue}</span>에 집중된다.",
                f"<span class='hl'>{dom_venue}</span>가 이 시기 주된 발표 창구로 기능했다 ({dom_share:.0%}).",
            ], seed_base + "::venue"))

        return " ".join(sents)

    else:
        opener = _EN_OPENERS[idx % len(_EN_OPENERS)].format(ys=ys, ye=ye)
        sents = []

        if n >= 60:
            sents.append(_pick([
                f"{opener} the output surges — <strong>{n}</strong> papers in just five years.",
                f"{opener} this stretch is the peak of production — <strong>{n}</strong> papers accumulate.",
                f"{opener} publication intensity climbs hard: <strong>{n}</strong> in this window alone.",
            ], seed_base + "::prod"))
        elif n >= 30:
            sents.append(_pick([
                f"{opener} <strong>{n}</strong> papers land in this stretch.",
                f"{opener} the tally reads <strong>{n}</strong> papers — fully active.",
                f"{opener} <strong>{n}</strong> papers are produced in these five years.",
            ], seed_base + "::prod"))
        elif n >= 10:
            sents.append(_pick([
                f"{opener} <strong>{n}</strong> papers were produced — a measured pace.",
                f"{opener} a steady <strong>{n}</strong> papers mark this period.",
                f"{opener} <strong>{n}</strong> papers close out the window.",
            ], seed_base + "::prod"))
        else:
            sents.append(_pick([
                f"{opener} the window is a quieter one — {n} papers in total.",
                f"{opener} {n} papers — an accumulation period rather than a burst.",
                f"{opener} only {n} papers land here; the real work may have been elsewhere.",
                f"{opener} output holds at {n} — a setup for what follows.",
            ], seed_base + "::prod"))

        if top_concepts:
            highlighted = [f"<span class='hl'>{c}</span>" for c in top_concepts[:2]]
            sents.append(_pick([
                f"The center of gravity rests on {', '.join(highlighted)}, threading through most of the era's output.",
                f"The working axis sits on {', '.join(highlighted)}.",
                f"Most of this stretch's work orbits {', '.join(highlighted)}.",
                f"The research frame for this period is {', '.join(highlighted)}.",
            ], seed_base + "::topic"))
            if len(top_concepts) > 2:
                sents.append(_pick([
                    f"{top_concepts[2]} emerges as a secondary strand.",
                    f"{top_concepts[2]} runs alongside as a parallel track.",
                    f"A secondary thread — {top_concepts[2]} — appears here.",
                ], seed_base + "::topic2"))

        if bbs_here:
            hit = bbs_here[0]
            sents.append(_pick([
                f"The face of the period is <em>\"{format_paper_title(hit['title'], 90)}\"</em> — {hit['venue']} {hit['year']}, {hit['cites']:,} cites, now a standard reference.",
                f"The anchor paper is <em>\"{format_paper_title(hit['title'], 90)}\"</em> ({hit['venue']} {hit['year']}, {hit['cites']:,} cites).",
                f"The era's signature work, <em>\"{format_paper_title(hit['title'], 90)}\"</em>, was published in {hit['venue']} {hit['year']} and has accumulated {hit['cites']:,} citations.",
            ], seed_base + "::bb1"))
            if len(bbs_here) > 1 and bbs_here[1]["cites"] >= 100:
                h2 = bbs_here[1]
                sents.append(_pick([
                    f"Close behind: <em>\"{format_paper_title(h2['title'], 75)}\"</em> ({h2['venue']} {h2['year']}, {h2['cites']:,}).",
                    f"A second anchor, <em>\"{format_paper_title(h2['title'], 75)}\"</em>, sits alongside ({h2['venue']} {h2['year']}, {h2['cites']:,}).",
                ], seed_base + "::bb2"))
        elif n >= 20:
            sents.append(_pick([
                "No single blockbuster defines this stretch; the citation ledger grows through sustained mid-tier production.",
                "The ledger grows not from a blockbuster but from a wide middle — many mid-weight papers, no single peak.",
                "Impact here is distributed — steady mid-tier works accumulate rather than one headline paper.",
            ], seed_base + "::nobb"))

        if coauths:
            names = ", ".join(f"<strong>{n_}</strong>" for n_, c in coauths)
            if len(coauths) == 1:
                sents.append(_pick([
                    f"The key working partner of this era is {names}.",
                    f"Most of the era's work rides on the partnership with {names}.",
                    f"The principal collaborator is {names}.",
                ], seed_base + "::co"))
            else:
                sents.append(_pick([
                    f"The era's working axis reads {names}.",
                    f"Core collaborators: {names}.",
                    f"The primary co-working axis ran through {names}.",
                ], seed_base + "::co"))

        if new_students:
            names = ", ".join(s["name"] for s in new_students[:4])
            more = f", + {len(new_students) - 4} more" if len(new_students) > 4 else ""
            sents.append(_pick([
                f"It is in this window that several junior coauthors appear to have begun their own careers under {family} — {names}{more}. The transition from solo work to group supervision is visible here.",
                f"New junior coauthors surface in this window — {names}{more}. The group around {family} starts taking shape here.",
                f"This period is when {family}'s cohort begins to form on paper: {names}{more}.",
            ], seed_base + "::stu"))

        if dom_venue and dom_share >= 0.55:
            sents.append(_pick([
                f"The publishing venue skews heavily — <span class='hl'>{dom_venue}</span> absorbed {dom_share:.0%} of the period's output.",
                f"{dom_share:.0%} of this period's output goes to <span class='hl'>{dom_venue}</span>.",
                f"<span class='hl'>{dom_venue}</span> dominates the venue mix in this window ({dom_share:.0%}).",
            ], seed_base + "::venue"))

        return " ".join(sents)


def build_phases(profile, author_papers, idf, max_idf, lang):
    windows = profile.get("topic_windows", [])
    venue_ws = profile.get("venue_windows", [])
    collab_ws = profile.get("collab_windows", [])
    v_idx = {(v["start"], v["end"]): v for v in venue_ws}
    c_idx = {(c["start"], c["end"]): c for c in collab_ws}
    phases = []
    total = len(windows)
    for i, win in enumerate(windows):
        k = (win["start"], win["end"])
        v = v_idx.get(k, {"mix": {}})
        c = c_idx.get(k, {"top_coauthors": [], "mean_n_authors": 0})
        win_phrases = phrases_for_window(author_papers, win["start"], win["end"], idf, max_idf, k=6)
        # Gloss ONLY what showed up as a distinctive TF-IDF phrase in the
        # window — raw blockbuster titles introduced false positives.
        glossary = lookup_glossary(win_phrases, lang, max_entries=4)

        # Paper-based fallback: the phase title surfaces up to 2 distinctive
        # phrases. For each of those, if the curated glossary didn't catch it,
        # attach the highest-cited in-window paper whose title contains all
        # the phrase's tokens, so readers see at least WHERE the term came
        # from ("Gel-Made Electro-Active Polymer Gripper, IROS 2018, 45c").
        title_phrases = win_phrases[:2]
        covered = {g["term"].lower() for g in glossary}
        for phr in title_phrases:
            if any(tok in covered for tok in phr.lower().split()) or phr.lower() in covered:
                continue
            # Avoid near-duplicate add if it's already a gloss term
            if phr.lower() in covered:
                continue
            # Find best paper whose title contains all phrase tokens
            tokens = [t for t in phr.lower().replace("-", " ").split() if len(t) > 1]
            if not tokens:
                continue
            candidates = []
            for p in author_papers:
                y = p.get("year")
                if not y or not (win["start"] <= y <= win["end"]):
                    continue
                title_l = (p.get("title") or "").lower().replace("-", " ")
                if all(tok in title_l for tok in tokens):
                    candidates.append(p)
            if not candidates:
                continue
            best = max(candidates, key=lambda x: x.get("cites", 0))
            t = best.get("title", "")
            t_short = t if len(t) <= 72 else t[:71].rstrip() + "…"
            if lang == "ko":
                gloss = f"대표 논문: <em>\"{t_short}\"</em> ({best.get('venue','?')} {best.get('year','')}, {best.get('cites',0):,}회)."
            else:
                gloss = f"from paper: <em>\"{t_short}\"</em> ({best.get('venue','?')} {best.get('year','')}, {best.get('cites',0):,} cites)."
            glossary.append({"term": phr, "gloss": gloss})
            if len(glossary) >= 5:
                break
        phases.append({
            "years": f"{win['start']} — {win['end']}",
            "id": ROMAN[i] if i < len(ROMAN) else str(i + 1),
            "title": phase_title(win, win_phrases, i, total, lang),
            "body": phase_body(profile, win, v, c, win_phrases, i, total, lang),
            "glossary": glossary,
        })
    return phases


JOURNAL_VENUES = {"T-RO", "IJRR", "RA-L", "T-Mech", "Sci-Rob", "SoRo"}


# --- scoring functions: return (score [0..1], detail dict)
def _score_role(p):
    rd = p.get("role_distribution", {})
    total = sum(rd.values()) or 1
    f = {k: v / total for k, v in rd.items()}
    cands = []
    if f.get("last", 0) >= 0.68:
        cands.append((min((f["last"] - 0.5) * 2.5, 1.0), {"kind": "last_dominant", "frac": round(f["last"],2)}))
    if f.get("first", 0) >= 0.28 and p["career_stats"]["span"] >= 15:
        cands.append((min((f["first"] - 0.12) * 3, 1.0), {"kind": "still_first", "frac": round(f["first"],2)}))
    if f.get("solo", 0) >= 0.12:
        cands.append((min(f["solo"] * 3, 1.0), {"kind": "solo_heavy", "frac": round(f["solo"],2)}))
    if not cands:
        return 0.0, {}
    return max(cands, key=lambda x: x[0])


def _score_venue(p):
    vws = p.get("venue_windows", [])
    if len(vws) < 3:
        return 0.0, {}
    def js(w):
        mix = w.get("mix", {})
        tot = sum(mix.values()) or 1
        return sum(v for k, v in mix.items() if k in JOURNAL_VENUES) / tot
    early = statistics.mean(js(w) for w in vws[:2])
    late = statistics.mean(js(w) for w in vws[-2:])
    shift = late - early
    if abs(shift) < 0.25:
        return 0.0, {}
    # stricter gradient: 0.25 -> 0.5, 0.45 -> 0.75, 0.60+ -> 1.0
    score = min((abs(shift) - 0.15) / 0.45, 1.0)
    direction = "conf_to_journal" if shift > 0 else "journal_to_conf"
    return score, {"early": round(early,2), "late": round(late,2), "shift": round(shift,2), "dir": direction}


def _score_blockbuster(p):
    bbs = p.get("blockbusters", [])
    if len(bbs) < 3:
        return 0.0, {}
    years = [b["year"] for b in bbs[:10] if b.get("year")]
    cites = [b["cites"] for b in bbs[:10] if b.get("cites")]
    if not years or not cites:
        return 0.0, {}
    yr_spread = max(years) - min(years) + 1
    span = p["career_stats"]["span"]
    ratio = cites[0] / cites[1] if len(cites) > 1 and cites[1] > 0 else 1.0
    if yr_spread <= 5 and len(years) >= 5:
        return 0.9, {"kind": "concentrated", "years": f"{min(years)}–{max(years)}", "spread": yr_spread}
    if ratio >= 2.5:
        return min((ratio - 1.5) / 3, 1.0), {"kind": "single_dominant", "ratio": round(ratio,1), "top_title": bbs[0]["title"][:50]}
    if yr_spread >= 20:
        return 0.55, {"kind": "spread", "spread": yr_spread, "span": span}
    return 0.0, {}


def _score_peak(p):
    ms = p.get("milestones", {})
    cs = p["career_stats"]
    peak = ms.get("peak_paper")
    if not peak or not peak.get("year"):
        return 0.0, {}
    rel = (peak["year"] - cs["first_year"]) / max(cs["span"] - 1, 1)
    if 0.25 <= rel <= 0.66:
        return 0.0, {}
    return min(abs(rel - 0.5) * 2, 1.0), {
        "rel": round(rel, 2),
        "when": "early" if rel < 0.25 else "late",
        "year": peak["year"],
        "title": peak["title"][:70],
        "cites": peak["cites"],
    }


def _score_half_life(p):
    hl = p.get("citation_half_life_years")
    if hl is None:
        return 0.0, {}
    diff = abs(hl - 10)
    if diff < 3:
        return 0.0, {}
    return min(diff / 10, 1.0), {"hl": hl, "kind": "young" if hl < 10 else "classic"}


def _score_productivity(p):
    ys = p.get("year_series", {})
    if not ys:
        return 0.0, {}
    years = sorted(int(y) for y in ys.keys())
    counts = [ys[str(y)]["n"] if str(y) in ys else ys[y]["n"] for y in years]
    if len(counts) < 5:
        return 0.0, {}
    mean = statistics.mean(counts)
    if mean == 0:
        return 0.0, {}
    sd = statistics.pstdev(counts)
    cv = sd / mean
    bursts = p.get("bursts", {})
    n_bursts = len(bursts.get("productivity", [])) + len(bursts.get("impact", []))
    thirds = max(len(counts) // 3, 1)
    first_third = sum(counts[:thirds]) / thirds
    last_third = sum(counts[-thirds:]) / thirds
    if cv >= 1.0 and n_bursts >= 2:
        return min(cv / 1.5, 1.0), {"kind": "bursty", "cv": round(cv, 2), "n_bursts": n_bursts}
    if last_third >= first_third * 3 and first_third >= 0.5:
        return 0.7, {"kind": "late_surge", "early": round(first_third,1), "late": round(last_third,1)}
    if first_third >= last_third * 2 and last_third > 0:
        return 0.55, {"kind": "early_heavy", "early": round(first_third,1), "late": round(last_third,1)}
    return 0.0, {}


def _score_venue_breadth(p):
    vws = p.get("venue_windows", [])
    venues = set()
    for w in vws:
        for v in w.get("mix", {}).keys():
            if v:
                venues.add(v)
    n = len(venues)
    if n >= 7:
        return min((n - 5) / 4, 1.0), {"kind": "generalist", "n": n, "venues": sorted(venues)}
    if n <= 2:
        return 0.6, {"kind": "specialist", "n": n, "venues": sorted(venues)}
    return 0.0, {}


def _score_collab(p):
    """Reserved for careers where collaboration structure is truly extreme —
    either a tight few-partner core, or a wide one-shot pattern. Most
    mid-career researchers have a 'top coauthor' relationship that is not
    itself distinctive, so thresholds are intentionally strict."""
    tops = p.get("top_repeat_coauthors", [])
    if len(tops) < 3:
        return 0.0, {}
    total = sum(t["count"] for t in tops)
    top3 = sum(t["count"] for t in tops[:3])
    share = top3 / total if total > 0 else 0
    top1 = tops[0]["count"]
    papers = p["career_stats"]["total_papers"]
    # require strong share AND strong absolute AND meaningful scale
    if share >= 0.55 and top1 >= 12 and papers >= 40:
        score = min((share - 0.35) * 2.2, 1.0)
        return score, {
            "kind": "fixed_partners",
            "share": round(share, 2),
            "top1": top1,
            "partners": [t["name"] for t in tops[:3]],
        }
    # "rotating": top coauthor appears only a handful of times, many partners
    if top1 <= 3 and len(tops) >= 15 and papers >= 40:
        return 0.5, {"kind": "rotating", "top1": top1, "n_partners": len(tops)}
    return 0.0, {}


def _score_centrality(p):
    ri = p.get("_rank_info", {})
    hub_rank = ri.get("rank_hub_degree")
    hub = ri.get("hub_degree")
    if hub_rank is None or hub is None:
        return 0.0, {}
    if hub_rank <= 30:
        return min((31 - hub_rank) / 30, 1.0), {"kind": "hub", "rank": hub_rank, "hub": hub}
    if hub <= 15:
        return 0.35, {"kind": "periphery", "rank": hub_rank, "hub": hub}
    return 0.0, {}


def _score_lineage(p, dynasty_map):
    students = p.get("likely_students", [])
    advisors = p.get("likely_advisors", [])
    topN = dynasty_map.get(p["name"], 0)
    n = len(students)
    if topN >= 2:
        return 0.95, {"kind": "dynasty", "topN": topN, "n_students": n, "top": [s["name"] for s in students[:4]]}
    if topN == 1:
        return 0.75, {"kind": "dynasty_x1", "topN": 1, "n_students": n, "top": [s["name"] for s in students[:4]]}
    if n >= 30:
        return 0.6, {"kind": "many_students", "n_students": n, "top": [s["name"] for s in students[:4]]}
    if advisors and n < 5:
        a = advisors[0]
        return 0.35, {"kind": "advisor_only", "advisor": a["name"],
                      "last_author_count": a.get("advisor_last_author_count", 0),
                      "early_copubs": a.get("early_copubs_as_our_first_author", 0)}
    return 0.0, {}


# --- narrative generators ---
# Each: (profile, detail, lang) -> {"title", "text"}

def _narrate_role(p, d, lang):
    kind = d.get("kind")
    frac = d.get("frac", 0)
    fam = p["name"].split()[-1]
    if kind == "last_dominant":
        if lang == "ko":
            return {
                "title": "거의 모든 논문 뒤에 서 있다 — 팀을 움직이는 사람",
                "text": (f"저자 위치 분포에서 마지막 저자 비율이 {frac:.0%}에 이른다. "
                         "본인이 직접 쓰기보다, 학생/포닥/협력자의 작업에 뒤에서 서명하고 그들을 앞세우는 방식으로 커리어를 운영해왔다는 뜻이다. "
                         "PI 전환을 이미 완료한 시그너처 — 신진 연구자에게는 '언제부터, 어떻게 뒤로 물러설 것인가'의 참고선이 된다."),
            }
        return {
            "title": "Last author on nearly everything — the team-mover",
            "text": (f"Last-author share sits at {frac:.0%}. "
                     "This career is run by signing at the back of other people's lead work rather than writing it out themselves — a PI-transition that has already closed. "
                     "For early-career readers: a reference line for when and how to step backwards."),
        }
    if kind == "still_first":
        if lang == "ko":
            return {
                "title": f"여전히 본인이 1저자로 쓴다 — 드문 포지션",
                "text": (f"{p['career_stats']['span']}년째 활동하는 연구자인데도 1저자 비율이 {frac:.0%}에 달한다. "
                         "랩을 키우는 대신 본인 손으로 계속 쓰는, 흔치 않은 스타일. "
                         "'시니어가 되어도 손을 놓지 않는다'는 선택이 한 커리어 안에서 어떻게 유지 가능한지의 드문 실증."),
            }
        return {
            "title": "Still the first author — a rare stance",
            "text": (f"{p['career_stats']['span']} years in, and the first-author share is still {frac:.0%}. "
                     "Rather than scaling out, this researcher keeps writing by hand. "
                     "A rare existence proof that you can stay the lead writer deep into a career."),
        }
    if kind == "solo_heavy":
        if lang == "ko":
            return {
                "title": "단독 저자 비율이 이례적으로 높다",
                "text": (f"전체 논문의 {frac:.0%}가 단독 저자다. "
                         "협업 위주의 로보틱스 커뮤니티에서 상당히 드문 프로파일 — 글 단독으로 밀어붙이는 생산성의 유형이다."),
            }
        return {
            "title": "Unusually high solo-author share",
            "text": (f"{frac:.0%} of papers carry this name alone. "
                     "Rare in a collaborative field — a sole-writer pattern of productivity."),
        }
    return {"title": "—", "text": ""}


def _narrate_venue(p, d, lang):
    early = d.get("early", 0)
    late = d.get("late", 0)
    direction = d.get("dir")
    if direction == "conf_to_journal":
        if lang == "ko":
            return {
                "title": "컨퍼런스 중심에서 저널 중심으로 이동",
                "text": (f"초기 논문 중 저널(T-RO/IJRR/RA-L 등) 비중은 {early:.0%}에 불과했지만, 최근 시기에는 {late:.0%}까지 올라왔다. "
                         "후반기 출판 전략이 '회의장에서의 속도'에서 '저널을 통한 정제'로 전환된 전형적 궤적. "
                         "신진 연구자에게 자연스러운 순서로 보일 수 있지만, 실제로는 모든 사람이 이 방향을 택하는 건 아니라는 점이 중요하다."),
            }
        return {
            "title": "From conference-driven to journal-driven",
            "text": (f"Journal share (T-RO/IJRR/RA-L and the like) was {early:.0%} early on; it's {late:.0%} now. "
                     "A classic late-career shift from conference velocity toward journal refinement — but one that not every strong career chooses."),
        }
    # journal_to_conf
    if lang == "ko":
        return {
            "title": "저널에서 출발해 점차 회의장 중심으로 이동",
            "text": (f"초기엔 저널 비중이 {early:.0%}로 높았지만, 최근은 {late:.0%}까지 내려왔다. "
                     "요즘 로보틱스가 컨퍼런스 속도에 무게중심을 두는 흐름과 궤를 같이하는 드문 유형이다."),
        }
    return {
        "title": "Gradual slide toward conference venues",
        "text": (f"Journal share was {early:.0%} early, now {late:.0%}. "
                 "Less common direction — aligning with the modern robotics preference for conference velocity."),
    }


def _narrate_blockbuster(p, d, lang):
    kind = d.get("kind")
    if kind == "concentrated":
        if lang == "ko":
            return {
                "title": f"상위 인용 논문들이 {d['years']}에 집중",
                "text": (f"최다 인용 논문 10편이 거의 모두 {d['years']} — 단 {d['spread']}년 안에 몰려 있다. "
                         "한 커리어의 임팩트 기반이 실질적으로 그 짧은 창에서 대부분 만들어졌다는 뜻. "
                         "'어느 시기에 무엇을 했느냐'가 '얼마나 오래 썼느냐'보다 결정적인 대표 사례."),
            }
        return {
            "title": f"Blockbusters cluster in {d['years']}",
            "text": (f"Top-10 cited papers fall almost entirely within {d['years']} — a {d['spread']}-year window. "
                     "The impact base of this career was forged in a narrow slice of time, "
                     "making it a case where <em>when</em> matters more than <em>how long</em>."),
        }
    if kind == "single_dominant":
        if lang == "ko":
            return {
                "title": "한 편에 실린 무게",
                "text": (f"최다 인용 논문이 2위 논문보다 약 {d['ratio']}배 더 많이 인용되었다 (\"{d['top_title']}…\"). "
                         "커리어의 중력이 사실상 그 한 편에 집중된 구조. "
                         "블록버스터가 곧 개인의 정체성이 되는 드문 유형."),
            }
        return {
            "title": "The weight of one paper",
            "text": (f"The top-cited paper is ~{d['ratio']}× the #2 (\"{d['top_title']}…\"). "
                     "The gravity of this career sits essentially on that one work — "
                     "a case where a blockbuster itself becomes the identity."),
        }
    if kind == "spread":
        if lang == "ko":
            return {
                "title": f"{d['spread']}년에 걸쳐 블록버스터가 분산",
                "text": (f"최다 인용 상위 10편이 {d['spread']}년이라는 넓은 창에 퍼져 있다. "
                         f"한 번의 히트가 아니라 긴 시간 동안 반복적으로 중요한 논문을 낸 드문 커리어다."),
            }
        return {
            "title": f"Blockbusters span {d['spread']} years",
            "text": (f"The top-10 cited papers are distributed across a {d['spread']}-year window. "
                     "Not one hit — a career that repeatedly produced significant work across a long span."),
        }
    return {"title": "—", "text": ""}


def _narrate_peak(p, d, lang):
    when = d.get("when")
    rel = d.get("rel", 0)
    title = d.get("title", "—")
    cites = d.get("cites", 0)
    year = d.get("year", "")
    if when == "early":
        if lang == "ko":
            return {
                "title": f"커리어 {rel:.0%} 지점에 이미 정점",
                "text": (f"최다 인용 논문(\"{title}\", {year}, {cites:,}회)이 커리어의 앞쪽 {rel:.0%} 지점에 놓여 있다. "
                         f"이후 {int((1-rel) * p['career_stats']['span'])}년은, 어떤 의미에서는 그 한 논문을 해석하고 확장한 시간으로 읽을 수 있다. "
                         "초년 블록버스터가 한 사람의 궤적 전체에 드리우는 긴 그림자의 드문 실례."),
            }
        return {
            "title": f"Peak paper at {rel:.0%} into the career",
            "text": (f"The top-cited paper (\"{title}\", {year}, {cites:,}) sits at {rel:.0%} of the career. "
                     f"The next {int((1-rel) * p['career_stats']['span'])} years can be read, in part, as an extended conversation with that single paper. "
                     "A rare case of how an early-career blockbuster casts a shadow over everything after."),
        }
    # late
    if lang == "ko":
        return {
            "title": f"커리어 후반({rel:.0%} 지점)에서야 정점",
            "text": (f"최다 인용 논문이 커리어의 {rel:.0%} 지점에 위치한다 (\"{title}\", {year}, {cites:,}회). "
                     "전반부가 준비기였고, 결실은 한참 뒤에 찾아온 유형 — "
                     "지금 초기 PI들에게는 '정점이 반드시 초년에 찍혀야 하는 건 아니다'라는 증거로 읽힌다."),
        }
    return {
        "title": f"Peak arrives late — {rel:.0%} of the way in",
        "text": (f"The top-cited paper sits at {rel:.0%} of the career (\"{title}\", {year}, {cites:,}). "
                 "The first half was preparation; the payoff came well later. "
                 "Evidence, for today's early-career PIs, that the peak is not required to land early."),
    }


def _narrate_half_life(p, d, lang):
    hl = d.get("hl")
    kind = d.get("kind")
    if kind == "classic":
        if lang == "ko":
            return {
                "title": "오래 전 작업이 아직도 인용을 끌어온다 — 고전이 된 유형",
                "text": (f"받는 인용의 중앙 연령이 {hl}년 — 다시 말해 지금 들어오는 인용의 절반 이상이 {hl}년 이전의 논문에서 나오고 있다. "
                         "초기작이 '고전'의 지위에 올랐다는 강한 신호. "
                         "빠르게 소비되는 분야에서 살아남은 드문 경우로, 문제 정의의 견고함이 시간에 대해 복리로 돌아온 셈."),
            }
        return {
            "title": "Old papers still drawing citations — a classic-style career",
            "text": (f"The median age of citations received is {hl} years — more than half of today's citations come from work that old or older. "
                     "Strong signal that the early work has reached classic status — problem framing that compounded against time."),
        }
    # young
    if lang == "ko":
        return {
            "title": "최근 작업이 지금의 인용을 끌어오고 있다",
            "text": (f"받는 인용의 중앙 연령이 {hl}년에 불과하다 — 지금이 가장 활발하게 읽히는 시기다. "
                     "과거에 기대지 않고 현재에서 재생산되고 있는 케이스. "
                     "후기 커리어가 '유지보수'가 아니라 '재도약'일 수 있다는 실례다."),
        }
    return {
        "title": "Recent work drives today's citations",
        "text": (f"Median citation age is only {hl} years — this career is most read <em>right now</em>. "
                 "Not living on the past — reproducing in the present. "
                 "Evidence that the late part of a career can be a reacceleration, not maintenance."),
    }


def _narrate_productivity(p, d, lang):
    kind = d.get("kind")
    if kind == "bursty":
        if lang == "ko":
            return {
                "title": f"쇄도와 숨고르기의 반복 — 간헐적 폭발형",
                "text": (f"연도별 출판량의 변동 계수(cv)가 {d['cv']}에 이르고, 식별된 피크 해가 {d['n_bursts']}번 있다. "
                         "매년 같은 속도로 쓰는 대신, 특정 시기에 폭발적으로 쏟아내고 다음 단계로 이동하는 리듬이다. "
                         "박사/포닥/안식년 경계에서 커리어가 계단식으로 도약한 흔적일 수 있다."),
            }
        return {
            "title": "Bursts and lulls — a discontinuous rhythm",
            "text": (f"Year-on-year output has a coefficient of variation of {d['cv']}, with {d['n_bursts']} distinct peak years. "
                     "This career moves in steps, not a steady line — possibly the signature of PhD/postdoc/sabbatical transitions leaving clear marks."),
        }
    if kind == "late_surge":
        if lang == "ko":
            return {
                "title": "후반부에 가속된 보기 드문 형태",
                "text": (f"초기 1/3의 평균 출판량은 연 {d['early']}편, 마지막 1/3은 연 {d['late']}편. "
                         "대부분의 커리어가 후반에 둔화되는데 반해, 이 사람은 후기에 오히려 폭이 넓어졌다. "
                         "제자 유입이나 새 주제 장악 때문일 가능성이 높다 — 신진 연구자 입장에서는 '늦게 달리기 시작해도 된다'는 하나의 증거."),
            }
        return {
            "title": "Late-career acceleration — uncommon",
            "text": (f"Early-third average: {d['early']} papers/year; last-third: {d['late']}/year. "
                     "Most careers decelerate late; this one widened. "
                     "Usually the fingerprint of incoming students or a newly captured topic — and, for early-career readers, proof that late starts are fine."),
        }
    if kind == "early_heavy":
        if lang == "ko":
            return {
                "title": "초반에 치고 나와 후반부는 선별 모드",
                "text": (f"초기 1/3 평균 연 {d['early']}편, 후기 1/3 연 {d['late']}편으로 생산량이 뚜렷이 줄어든다. "
                         "'젊을 때 많이 쓰고, 나이들면서 큐레이션으로 전환'하는 유형의 전형. "
                         "생산성 감소가 쇠퇴가 아니라 선택일 수 있다는 점을 상기시킨다."),
            }
        return {
            "title": "Front-loaded output, then curation mode",
            "text": (f"Early-third {d['early']}/yr; late-third {d['late']}/yr — a clear tapering. "
                     "The 'write a lot young, curate when older' shape. A reminder that lowered output is sometimes a choice, not a decline."),
        }
    return {"title": "—", "text": ""}


def _narrate_breadth(p, d, lang):
    kind = d.get("kind")
    n = d.get("n", 0)
    venues = ", ".join(d.get("venues", [])[:7])
    if kind == "generalist":
        if lang == "ko":
            return {
                "title": f"9개 venue 중 {n}개에 논문 — 제너럴리스트 프로파일",
                "text": (f"등장한 venue: {venues}. "
                         "특정 커뮤니티 하나에 박혀 있지 않고, 인접 영역까지 꾸준히 교류해온 흔적이다. "
                         "분야 횡단이 주는 기회와 비용을 모두 감수해야 가능한 드문 스타일."),
            }
        return {
            "title": f"Papers in {n}/9 atlas venues — a generalist",
            "text": (f"Venues visited: {venues}. "
                     "Not parked in a single community but cross-publishing into adjacent ones — a style that pays and costs simultaneously."),
        }
    if lang == "ko":
        return {
            "title": f"단 {n}개 venue에 집중 — 전공 스페셜리스트",
            "text": (f"{venues} — 이 venue들에만 거의 모든 논문이 실렸다. "
                     "좁은 커뮤니티에 깊이 박혀 있는 드문 프로파일. "
                     "그 대신 그 분야 내부에서의 영향력이 집중적이다."),
        }
    return {
        "title": f"Concentrated in only {n} venues",
        "text": (f"{venues} — almost the entire record sits in these. "
                 "A specialist embedded deep in a narrow community, trading breadth for concentration of influence."),
    }


def _narrate_collab(p, d, lang):
    kind = d.get("kind")
    if kind == "fixed_partners":
        partners = ", ".join(d.get("partners", []))
        share = d.get("share", 0)
        if lang == "ko":
            return {
                "title": "고정 파트너 기반의 커리어",
                "text": (f"상위 3명의 공저자({partners})가 본인의 반복 협업 중 {share:.0%}를 차지한다. "
                         "커리어의 상당 부분이 소수의 강한 동료 관계에 의해 지탱되었다는 뜻. "
                         "'누구와 오래 할 것인가'가 '무엇을 할 것인가'만큼 중요함을 보여주는 실례."),
            }
        return {
            "title": "A career built on fixed partnerships",
            "text": (f"The top three coauthors ({partners}) account for {share:.0%} of repeat collaborations. "
                     "Much of this career rests on a small set of strong, sustained working relationships — "
                     "a reminder that <em>who</em> you choose to work with matters as much as <em>what</em> you work on."),
        }
    if kind == "rotating":
        if lang == "ko":
            return {
                "title": "반복 공저자가 얕다 — 매번 새 팀",
                "text": (f"최다 공저자와도 {d['top1']}회밖에 함께 쓰지 않았다. 다수의 단발 협업자와 일하는 스타일. "
                         "네트워크가 넓지만 깊지는 않은 프로파일. 유행에 맞춰 움직이는 유연한 커리어 모델."),
            }
        return {
            "title": "Thin repeat-collaborators — a rotating cast",
            "text": (f"Even the most frequent coauthor appears only {d['top1']} times. Lots of one-off partnerships. "
                     "A wide-but-not-deep network — a flexible career that moves with the field."),
        }
    return {"title": "—", "text": ""}


def _narrate_centrality(p, d, lang):
    kind = d.get("kind")
    if kind == "hub":
        if lang == "ko":
            return {
                "title": "공저자 네트워크의 핵 — 모두가 거쳐간 허브",
                "text": (f"공저자 네트워크에서 이 사람과 연결된 고유 연구자 수는 {d['hub']}명이며, 이는 natural pool 전체 중 상위 {d['rank']}위에 해당한다. "
                         "주제보다 사람으로 커리어가 성립한 케이스 — 당대 로보틱스 협업 지도가 이 이름을 거쳐가지 않고는 그려지지 않는다."),
            }
        return {
            "title": "A hub of the coauthor network — everyone passes through",
            "text": (f"This researcher is connected to {d['hub']} unique coauthors — rank #{d['rank']} in the natural pool. "
                     "A career that stands more on people than on a single topic — you can't draw a map of the era's collaborations without this name on it."),
        }
    if lang == "ko":
        return {
            "title": "공저 네트워크 밖의 자체 궤도",
            "text": (f"공저자 연결 수가 {d['hub']}에 불과한 독립적 프로파일. "
                     "커뮤니티의 중심을 통과하지 않고도 성립 가능한 커리어의 한 예."),
        }
    return {
        "title": "Own orbit outside the coauthor network",
        "text": (f"Only {d['hub']} coauthor ties — an independent profile. "
                 "A reminder that a legitimate career can sit off the community's central graph."),
    }


def _narrate_lineage(p, d, lang):
    kind = d.get("kind")
    n = d.get("n_students", 0)
    if kind in ("dynasty", "dynasty_x1"):
        topN = d.get("topN", 0)
        top = ", ".join(d.get("top", []))
        if lang == "ko":
            return {
                "title": f"배출한 제자가 다시 top 순위로 진입 — 학파가 재생산되는 중",
                "text": (f"공저 패턴으로 추정되는 제자 {n}명 중 {topN}명이 본 랭킹 안에 다시 들어와 있다 (예: {top}). "
                         "'대가가 대가를 기른다'는 드문 실증 케이스. "
                         "개인 커리어를 넘어 학맥 자체가 성립해가는 구간이다."),
            }
        return {
            "title": "Students have re-entered the ranking — a dynasty forming",
            "text": (f"Of the {n} likely students by coauthor signal, {topN} appear again inside this ranking (e.g. {top}). "
                     "A rare case where mastery has reproduced itself — the career has expanded beyond the individual into a school."),
        }
    if kind == "many_students":
        top = ", ".join(d.get("top", []))
        if lang == "ko":
            return {
                "title": f"추정 제자 {n}명 — 논문이 아닌 사람의 배출로 읽히는 커리어",
                "text": (f"공저 패턴이 {n}명 규모의 후배 그룹을 지시하며, 대표 이름으로는 {top} 등이 있다. "
                         "결국 한 연구자가 분야에 남기는 가장 오래 가는 흔적은, 자신이 길러낸 또 다른 연구자들이라는 주장의 실증."),
            }
        return {
            "title": f"{n} likely students — a career read through people, not papers",
            "text": (f"Coauthor patterns point to a cohort of {n}, including names like {top}. "
                     "The longest-lasting mark a researcher leaves is, in the end, the other researchers they trained."),
        }
    if kind == "advisor_only":
        a = d.get("advisor", "")
        if lang == "ko":
            return {
                "title": f"{a}의 네트워크 안에서 출발한 연구자",
                "text": (f"커리어 초기 본인이 1저자인 논문 {d.get('early_copubs', 0)}편 중 {d.get('last_author_count', 0)}편에 {a}가 마지막저자로 서 있다. "
                         f"이 출발점이 지금까지의 방향을 상당 부분 결정했다는 공저 신호가 뚜렷하다."),
            }
        return {
            "title": f"Launched inside {a}'s network",
            "text": (f"Of {d.get('early_copubs', 0)} first-author papers in the opening years, {d.get('last_author_count', 0)} carry {a} as last author. "
                     f"The coauthor signal is unmistakable: this career's direction was set within {a}'s orbit."),
        }
    return {"title": "—", "text": ""}


THEME_SCORERS = [
    ("role_signature", _score_role, _narrate_role),
    ("venue_evolution", _score_venue, _narrate_venue),
    ("blockbuster_concentration", _score_blockbuster, _narrate_blockbuster),
    ("peak_position", _score_peak, _narrate_peak),
    ("citation_half_life", _score_half_life, _narrate_half_life),
    ("productivity_rhythm", _score_productivity, _narrate_productivity),
    ("cross_venue_breadth", _score_venue_breadth, _narrate_breadth),
    ("collaboration_rhythm", _score_collab, _narrate_collab),
    ("community_centrality", _score_centrality, _narrate_centrality),
    ("lineage", None, _narrate_lineage),  # scored separately w/ dynasty map
]


def select_secondary_themes(profile, dynasty_map, usage_counter, lang):
    """Return two theme dicts (title, text) picked from the 10-pool with
    diversity awareness across the run."""
    scored = []
    for key, scorer, narrator in THEME_SCORERS:
        if scorer is None and key == "lineage":
            s, det = _score_lineage(profile, dynasty_map)
        else:
            s, det = scorer(profile)
        if s <= 0 or not det:
            continue
        # diversity penalty — stronger cap to prevent any single theme from
        # dominating the secondary slot across the cohort.
        penalty = min(usage_counter.get(key, 0) * 0.015, 0.35)
        scored.append((s - penalty, s, key, det, narrator))
    scored.sort(key=lambda x: -x[0])
    picks = []
    for adj, raw, key, det, narrator in scored:
        if len(picks) >= 2:
            break
        blob = narrator(profile, det, lang)
        if not blob or not blob.get("text"):
            continue
        blob["_key"] = key
        picks.append(blob)
        usage_counter[key] = usage_counter.get(key, 0) + 1
    return picks


def build_themes(profile, author_papers, idf, max_idf, meta_dynasty, lang,
                 usage_counter=None):
    themes = []
    cs = profile["career_stats"]
    pivot = profile.get("pivot_score", 0)
    td = profile.get("team_drift", {})
    students = profile.get("likely_students", [])
    advisors = profile.get("likely_advisors", [])
    family = profile["name"].split()[-1]
    windows = profile.get("topic_windows", [])
    n_windows = len(windows)

    career_phrases = phrases_for_span(author_papers, idf, max_idf, k=5)
    early_phr = phrases_for_window(author_papers, windows[0]["start"], windows[0]["end"], idf, max_idf, k=2) if windows else []
    late_phr = phrases_for_window(author_papers, windows[-1]["start"], windows[-1]["end"], idf, max_idf, k=2) if windows else []
    early = early_phr
    late = late_phr
    cont = career_phrases  # use distinctive career-wide phrases as anchor candidates

    # Theme 1
    if pivot >= 0.4 and early and late:
        if lang == "ko":
            themes.append({
                "num": "01",
                "title": f"{early[0]}에서 {late[0]}까지 — 10년마다 무대를 바꾼다",
                "text": (
                    f"피벗 점수 {pivot:.2f}는 본 조사 상위권에 해당한다. "
                    f"같은 이름으로 서명이 이어졌을 뿐, 실제로 다루는 문제는 몇 번이나 통째로 갈렸다. "
                    f"초기에는 {early[0]}, 지금은 {late[0]} — 그 사이에 도구, 평가 방법, 함께 일하는 사람까지 이동한다. "
                    "재창조의 연쇄가 이 사람의 경력을 지탱하는 엔진이다."
                ),
            })
        else:
            themes.append({
                "num": "01",
                "title": f"From {early[0]} to {late[0]} — the stage changes each decade",
                "text": (
                    f"A pivot score of {pivot:.2f} places them at the high end of our sample. "
                    f"The name above the papers stayed constant, but the underlying problem was rewritten several times. "
                    f"Early: {early[0]}. Now: {late[0]}. "
                    "Tools, benchmarks, and working partners all shifted with each turn. "
                    "Reinvention is the engine that powered this career."
                ),
            })
    elif cont:
        anchor = cont[0]
        if lang == "ko":
            themes.append({
                "num": "01",
                "title": f"{anchor}라는 축은 한 번도 흔들리지 않았다",
                "text": (
                    f"{n_windows}개 5년 구간 중 대부분에서 {anchor}가 상위 주제로 반복 등장한다. "
                    "주변 토픽은 바뀌고 도구는 세대가 지나면서 교체되었지만, 중심축은 단 한 번도 비켜선 적이 없다. "
                    "임팩트를 폭이 아닌 깊이로 만들어낸 전형적인 장인형 경력."
                ),
            })
        else:
            themes.append({
                "num": "01",
                "title": f"The {anchor} anchor never moved",
                "text": (
                    f"{anchor} appears among the top topics in most of the {n_windows} 5-year windows. "
                    "Adjacent topics drift, tools get replaced generation by generation, but the central axis never yields. "
                    "A classic artisan's arc — impact achieved through depth, not breadth."
                ),
            })
    elif early:
        if lang == "ko":
            themes.append({
                "num": "01",
                "title": f"{early[0]}에서 시작해 지금까지",
                "text": (
                    f"첫 주제 선택이 이 경력의 색깔을 그대로 결정지었다. "
                    f"세부 변주는 존재하지만, DNA는 {early[0]} 그대로다. "
                    "데이터가 길게 안정적인 궤적을 보여주는 드문 유형."
                ),
            })
        else:
            themes.append({
                "num": "01",
                "title": f"It started with {early[0]} — and it still does",
                "text": (
                    f"The opening bet set the color of this career. Variations exist, but the DNA is {early[0]}. "
                    "A rare case where the data shows a long, stable trajectory with almost no turn."
                ),
            })

    # Themes 2 & 3: picked from the 10-theme pool, diversity-aware across the run.
    if usage_counter is None:
        usage_counter = {}
    picks = select_secondary_themes(profile, meta_dynasty, usage_counter, lang)
    for i, p_theme in enumerate(picks, start=2):
        themes.append({
            "num": f"0{i}",
            "title": p_theme["title"],
            "text": p_theme["text"],
        })

    return themes


def pullquote(profile, lang, author_papers=None, idf=None, max_idf=None):
    cs = profile["career_stats"]
    pivot = profile.get("pivot_score", 0)
    students = profile.get("likely_students", [])
    ms = profile.get("milestones", {})
    td = profile.get("team_drift", {})
    advisors = profile.get("likely_advisors", [])

    seed = profile["name"]

    # Career-wide anchor phrase for more specific quotes
    anchor = ""
    if author_papers is not None and idf is not None:
        ps = phrases_for_span(author_papers, idf, max_idf, k=3)
        anchor = ps[0] if ps else ""

    # Pick by priority: the most distinctive trait wins.
    if pivot >= 0.45:
        return _pick(
            [
                "도구는 버려도, 질문은 그대로 남는다.",
                "같은 이름, 다른 질문 — 10년마다.",
                "익숙해지기 전에 이동했다.",
                "무대를 바꾸는 것이 이 커리어의 방법론이었다.",
                "바뀌는 것은 방법, 남는 것은 감각.",
            ], seed) if lang == "ko" else _pick(
            [
                "Tools change. The question stays.",
                "Same name, different question — once a decade.",
                "Moved before getting comfortable.",
                "The method here is changing methods.",
                "What changes is how; what stays is why.",
            ], seed)

    if len(students) >= 30:
        return _pick(
            [
                f"{len(students)}명을 내보낸 것이, 진짜 결과물이다.",
                "가장 오래 남는 결과물은 사람이다.",
                "논문 숫자가 흐려져도, 지도한 연구자 목록은 남는다.",
                "커리어를 사람으로 읽어야 하는 경우.",
            ], seed) if lang == "ko" else _pick(
            [
                f"The {len(students)} people launched — that is the real output.",
                "What outlasts citations is the roster of people trained.",
                "A career best read in students, not in papers.",
                "Careers you measure in other careers.",
            ], seed)

    if "first_500cite" in ms and ms["first_500cite"]["gap_from_first"] <= 4:
        g = ms["first_500cite"]["gap_from_first"]
        gap_txt = "첫 논문부터" if g == 0 else f"시작 {g}년 차에"
        gap_en = "from the very first paper" if g == 0 else f"in year {g}"
        return _pick(
            [
                f"{gap_txt} 나온 한 편이, 나머지를 결정한다.",
                f"커리어의 중력은 {gap_txt} 쏜 논문 하나에서 나온다.",
                "처음 5년 안에 착지한 주제가 전부를 끌고 간다.",
                "초반에 제대로 꽂으면 나머지는 관성이다.",
            ], seed) if lang == "ko" else _pick(
            [
                f"One paper {gap_en} — it set the rest of the career.",
                f"The gravity of this career comes from an early anchor {gap_en}.",
                "Land the big one in the first five years; the rest is momentum.",
                "An early anchor carries a whole career.",
            ], seed)

    if pivot < 0.18 and cs["total_papers"] >= 150 and anchor:
        return _pick(
            [
                f"하나의 문제, {cs['span']}년.",
                f"{anchor} — {cs['span']}년에 걸친 복리.",
                "한 우물을 끝까지 판다는 것.",
                "깊이는 시간이 만드는 덕목이다.",
            ], seed) if lang == "ko" else _pick(
            [
                f"One question, {cs['span']} years.",
                f"{anchor}, compounded for {cs['span']} years.",
                "To push one lane all the way down.",
                "Depth is a virtue that time underwrites.",
            ], seed)

    if cs["total_papers"] >= 250:
        return _pick(
            [
                f"{cs['total_papers']}편 — 다작은 지속성의 다른 이름이다.",
                "볼륨은 품질이 아니라 시간의 이름이다.",
                "많이 쓴다는 것은, 오래 버틴다는 뜻이다.",
                "누적이 어떤 통찰보다 강할 수 있다.",
            ], seed) if lang == "ko" else _pick(
            [
                f"{cs['total_papers']} papers — volume is another word for endurance.",
                "Volume is not quality — it is the name for sustained time.",
                "To write a lot is to keep showing up.",
                "Accumulation can outweigh insight.",
            ], seed)

    td_e, td_l = td.get("early_mean_n_authors"), td.get("late_mean_n_authors")
    if td_e and td_l and td_l - td_e > 1.5:
        return _pick(
            [
                "혼자 쓰던 사람이, 랩을 이끄는 사람이 되었다.",
                "한 명에서 시작해 팀이 된 궤적.",
                "저자 수가 늘어난다는 것은, 스타일이 바뀌었다는 뜻이다.",
            ], seed) if lang == "ko" else _pick(
            [
                "The solo writer became the group leader.",
                "From one author per paper to many.",
                "Author counts grew because the style did.",
            ], seed)

    if advisors and cs["span"] < 20:
        adv = advisors[0]["name"]
        return _pick(
            [
                f"{adv}의 네트워크에서 시작해, 자신의 궤도로 확장해갔다.",
                "스승의 우산 아래에서 출발해, 자신의 지도를 그리는 중.",
                "받은 것 위에 쌓는다는 것.",
            ], seed) if lang == "ko" else _pick(
            [
                f"Launched inside {adv}'s network; now tracing an own path.",
                "Starting under an umbrella, now drawing their own map.",
                "Building on what was handed down.",
            ], seed)

    if cs["h_index"] >= 70:
        return _pick(
            [
                f"h={cs['h_index']} — 복리의 결과물이다.",
                "임팩트는 이벤트가 아니라 상태다.",
                "지속이 인용을 만든다.",
            ], seed) if lang == "ko" else _pick(
            [
                f"h={cs['h_index']} — a compound result.",
                "Impact is not an event; it is a state.",
                "Staying is what builds the ledger.",
            ], seed)

    # Generic — but varied per researcher
    if anchor and lang == "ko":
        ko_generic_with_anchor = [
            f"{anchor} 하나에 인생을 걸었다.",
            f"{anchor}라는 축이 이 커리어의 모든 것을 지탱한다.",
            f"{anchor}가 답이자 방법이었다.",
        ]
        fallback_ko = [
            "도구가 바뀌어도 살아남는 질문을 고르라.",
            "평균이 아닌, 지속의 결과물.",
            "빠르게 가지 않아도 멀리 간다.",
            "구조의 일부가 되는 방법은, 오래 남는 것이다.",
            "데이터가 먼저 말하게 두는 커리어.",
        ]
        return _pick(ko_generic_with_anchor + fallback_ko, seed)
    if anchor and lang == "en":
        en_generic_with_anchor = [
            f"Bet a career on {anchor}.",
            f"A whole career held up by {anchor}.",
            f"{anchor} was both the answer and the method.",
        ]
        fallback_en = [
            "Pick the question that survives tooling changes.",
            "Not fast, but far.",
            "Becoming part of the structure by outlasting it.",
            "Not the average — the persistence.",
            "Let the data speak first.",
        ]
        return _pick(en_generic_with_anchor + fallback_en, seed)

    fallback_ko = [
        "도구가 바뀌어도 살아남는 질문을 고르라.",
        "평균이 아닌, 지속의 결과물.",
        "빠르게 가지 않아도 멀리 간다.",
        "데이터가 먼저 말하게 두는 커리어.",
    ]
    fallback_en = [
        "Pick the question that survives tooling changes.",
        "Not fast, but far.",
        "Let the data speak first.",
        "Not the average — the persistence.",
    ]
    return _pick(fallback_ko if lang == "ko" else fallback_en, seed)


def build_highlights(profile, k=8):
    bbs = profile.get("blockbusters", [])[:k]
    return [
        {
            "year": b["year"],
            "venue": b.get("venue", ""),
            "title": b["title"],
            "cites": b["cites"],
        }
        for b in bbs
    ]


def build_venue_year_series(author_papers):
    """Return {'years': [y1,...], 'venues': ['ICRA',...], 'matrix': {venue: [counts by year]}}."""
    if not author_papers:
        return {"years": [], "venues": [], "matrix": {}}
    yrs = [p["year"] for p in author_papers if p.get("year")]
    if not yrs:
        return {"years": [], "venues": [], "matrix": {}}
    y0, y1 = min(yrs), max(yrs)
    years = list(range(y0, y1 + 1))
    counts: dict[str, list[int]] = {}
    for p in author_papers:
        y = p.get("year")
        v = (p.get("venue") or "").strip() or "?"
        if not y or y < y0 or y > y1:
            continue
        if v not in counts:
            counts[v] = [0] * len(years)
        counts[v][y - y0] += 1
    # Order venues by total descending so the most prominent venue shows on top
    venue_totals = [(v, sum(counts[v])) for v in counts]
    venue_totals.sort(key=lambda x: -x[1])
    ordered = [v for v, _ in venue_totals]
    matrix = {v: counts[v] for v in ordered}
    return {"years": years, "venues": ordered, "matrix": matrix}


def build_lineage(profile, lang):
    advisors = profile.get("likely_advisors", [])[:3]
    students = profile.get("likely_students", [])
    return {
        "advisors": advisors,
        "students": students,
        "students_shown": students[:12],
        "students_rest": max(len(students) - 12, 0),
    }


def build_page_data(profile, author_papers, idf, max_idf, meta, lang, meta_dynasty,
                    usage_counter=None):
    archetype_map = {a["name"]: a["archetype"] for a in meta["archetype_assignments"]}
    return {
        "tagline": tagline(profile, lang, author_papers, idf, max_idf),
        "oneLine": one_liner(profile, lang, author_papers, idf, max_idf),
        "facts": build_facts(profile, author_papers, idf, max_idf, archetype_map, lang),
        "phases": build_phases(profile, author_papers, idf, max_idf, lang),
        "themes": build_themes(profile, author_papers, idf, max_idf, meta_dynasty, lang,
                               usage_counter=usage_counter),
        "pullquote": pullquote(profile, lang, author_papers, idf, max_idf),
        "highlights": build_highlights(profile),
        "lineage": build_lineage(profile, lang),
        "venue_year_series": build_venue_year_series(author_papers),
    }


# -----------------------------------------------------------------------------
# HTML template
# -----------------------------------------------------------------------------

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
  font-size: 16px;
  line-height: 1.65;
  word-break: keep-all;
  -webkit-font-smoothing: antialiased;
}
body {
  background-image:
    radial-gradient(circle at 20% 30%, rgba(193, 68, 14, 0.04) 0%, transparent 40%),
    radial-gradient(circle at 80% 70%, rgba(45, 74, 62, 0.04) 0%, transparent 40%);
  min-height: 100vh;
  padding: 40px 24px 96px;
}
.grain {
  position: fixed; inset: 0; pointer-events: none;
  opacity: 0.35; mix-blend-mode: multiply; z-index: 1;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/><feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.08 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
}
.container { max-width: 1100px; margin: 0 auto; position: relative; z-index: 2; }

.masthead {
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--ink);
  padding: 14px 0 12px; margin-bottom: 32px;
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 24px; flex-wrap: wrap;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
}
.masthead .brand {
  font-family: 'Fraunces', 'Noto Serif KR', serif;
  font-weight: 900; font-style: italic;
  font-size: 1.4rem; color: var(--ink);
  letter-spacing: -0.02em;
  text-transform: none;
}
.masthead .brand a { color: inherit; text-decoration: none; }
.masthead .brand .amp { color: var(--accent); }
.masthead .right { display: flex; gap: 16px; align-items: baseline; }
.back-link { color: var(--muted); text-decoration: none; border-bottom: 1px dotted currentColor; }
.back-link:hover { color: var(--ink); }

.lang-tabs { display: inline-flex; gap: 2px; align-items: center; }
.lang-tab {
  padding: 2px 8px; cursor: pointer;
  text-decoration: none; color: var(--muted);
  border: 1px solid transparent; font-size: 0.66rem;
}
.lang-tab.active { color: var(--paper); background: var(--ink); border-color: var(--ink); }
.lang-tab:not(.active):hover { color: var(--ink); border-color: var(--muted); }
.lang-sep { color: var(--muted); opacity: 0.35; font-size: 0.6rem; }

.rank-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: var(--muted);
  letter-spacing: 0.1em; text-transform: uppercase;
  margin-bottom: 8px;
}

.profile-head {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 56px;
  padding-bottom: 40px;
  margin-bottom: 40px;
  border-bottom: 1px solid var(--ink);
  align-items: start;
}
.profile-name {
  font-family: 'Fraunces', 'Noto Serif KR', serif;
  font-weight: 500;
  font-size: clamp(2.4rem, 5vw, 4rem);
  line-height: 0.98;
  letter-spacing: -0.03em;
  margin-bottom: 18px;
}
.profile-name .given { display: block; font-weight: 400; font-style: italic; opacity: 0.7; font-size: 0.55em; margin-bottom: 4px; }
.profile-name .family { display: block; }
.profile-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--accent);
  margin-bottom: 20px;
}
.profile-oneline {
  font-family: 'Noto Serif KR', 'Fraunces', serif;
  font-size: 1.15rem; line-height: 1.55;
  letter-spacing: -0.01em;
}
.profile-facts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  align-self: start;
  border-left: 2px solid var(--ink);
  padding-left: 16px;
}
.profile-facts dt {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 0.64rem;
  color: var(--muted);
  padding: 8px 0 0;
  white-space: nowrap;
}
.profile-facts dd {
  font-size: 0.82rem;
  padding: 8px 0;
  border-bottom: 1px dotted rgba(26, 22, 20, 0.2);
  font-family: 'Pretendard', sans-serif;
}
.profile-facts dt { border-bottom: 1px dotted rgba(26, 22, 20, 0.2); padding-bottom: 8px; }
.profile-facts dd strong { color: var(--accent); font-weight: 700; }

.section { margin-bottom: 56px; }
.section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--muted);
  margin-bottom: 12px;
  display: flex; align-items: center; gap: 12px;
}
.section-label::before {
  content: ''; width: 24px; height: 1px; background: var(--accent);
}
.section-title {
  font-family: 'Noto Serif KR', 'Fraunces', serif;
  font-weight: 500;
  font-size: 1.5rem; line-height: 1.35;
  letter-spacing: -0.01em;
  margin-bottom: 24px;
  max-width: 40ch;
}

/* venue-year plot */
.venue-plot-box {
  position: relative; width: 100%; height: 300px;
  background: var(--card); padding: 20px 24px 12px;
  border-top: 1px solid var(--ink);
  border-bottom: 1px solid rgba(26,22,20,0.15);
}
.venue-plot-caption {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem; color: var(--muted);
  letter-spacing: 0.06em;
  margin-top: 8px;
}

/* phases */
.phases { display: grid; gap: 0; border-top: 1px solid var(--ink); }
.phase {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 32px;
  padding: 28px 0;
  border-bottom: 1px solid rgba(26, 22, 20, 0.2);
  transition: background 0.2s;
}
.phase:hover { background: var(--paper-2); }
.phase-meta { font-family: 'JetBrains Mono', monospace; }
.phase-years {
  font-size: 1.2rem; font-weight: 700;
  color: var(--accent); letter-spacing: -0.01em;
  margin-bottom: 6px;
}
.phase-id {
  font-size: 0.6rem; text-transform: uppercase;
  letter-spacing: 0.15em; color: var(--muted);
}
.phase-body h4 {
  font-family: 'Noto Serif KR', 'Fraunces', serif;
  font-weight: 600; font-size: 1.2rem;
  line-height: 1.4; letter-spacing: -0.01em;
  margin-bottom: 12px;
}
.phase-body p {
  font-size: 0.95rem; line-height: 1.75;
  max-width: 70ch;
}
.phase-body .hl {
  background: linear-gradient(180deg, transparent 60%, var(--highlight) 60%);
  padding: 0 2px; font-weight: 500;
}
.phase-body em {
  font-style: italic;
  font-family: 'Fraunces', 'Noto Serif KR', serif;
  color: var(--accent-2);
}
.phase-body strong { color: var(--accent); font-weight: 700; }
.phase-glossary {
  margin-top: 14px;
  background: var(--paper-2);
  border-left: 2px solid var(--accent-2);
  padding: 10px 14px;
}
.phase-glossary h5 {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.66rem; text-transform: uppercase;
  letter-spacing: 0.12em; color: var(--muted);
  margin-bottom: 8px;
}
.phase-glossary ul { list-style: none; padding: 0; margin: 0; }
.phase-glossary li {
  font-size: 0.85rem; line-height: 1.55;
  padding: 3px 0;
}
.phase-glossary li strong {
  color: var(--accent-2); font-weight: 700;
  font-family: 'Fraunces', serif;
  margin-right: 6px;
}

/* themes */
.themes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1px; background: var(--ink); border: 1px solid var(--ink);
}
.theme { background: var(--paper); padding: 28px 24px; }
.theme-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 2.4rem; font-weight: 500;
  color: var(--accent);
  line-height: 1; margin-bottom: 12px;
  letter-spacing: -0.02em;
}
.theme h5 {
  font-family: 'Noto Serif KR', 'Fraunces', serif;
  font-weight: 600; font-size: 1.05rem;
  line-height: 1.4; margin-bottom: 10px;
  letter-spacing: -0.01em;
}
.theme p { font-size: 0.9rem; line-height: 1.7; color: var(--muted); }

/* pullquote */
.pullquote {
  font-family: 'Noto Serif KR', 'Fraunces', serif;
  font-weight: 400;
  font-size: clamp(1.2rem, 2.2vw, 1.6rem);
  line-height: 1.5; max-width: 52ch;
  margin: 40px auto;
  padding: 36px 24px;
  border-top: 1px solid var(--ink);
  border-bottom: 1px solid var(--ink);
  text-align: center; position: relative;
  letter-spacing: -0.01em;
}
.pullquote::before {
  content: '"';
  font-family: 'Fraunces', serif;
  font-size: 4rem; color: var(--accent);
  position: absolute; top: -10px; left: 50%;
  transform: translateX(-50%);
  background: var(--paper); padding: 0 12px; line-height: 1;
}

/* highlights */
.highlights { display: grid; grid-template-columns: 1fr; gap: 0; }
.hl-item {
  display: grid; grid-template-columns: auto 1fr auto;
  gap: 20px; padding: 14px 0;
  border-bottom: 1px dotted rgba(26, 22, 20, 0.25);
  align-items: baseline;
}
.hl-year {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem; font-weight: 700;
  color: var(--accent); min-width: 60px;
}
.hl-title { font-family: 'Fraunces', serif; font-size: 1rem; line-height: 1.4; }
.hl-title .venue {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--muted);
  margin-right: 8px; padding: 2px 6px;
  background: var(--paper-2);
  border: 1px solid rgba(26, 22, 20, 0.2);
}
.hl-cites { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--muted); white-space: nowrap; }
.hl-cites strong { color: var(--ink); font-weight: 700; font-size: 0.88rem; }

/* lineage */
.lineage-grid {
  display: grid; grid-template-columns: 1fr 1.4fr;
  gap: 40px;
}
.lineage-block h5 {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem; text-transform: uppercase;
  letter-spacing: 0.14em; color: var(--muted);
  margin-bottom: 12px;
}
.lineage-item {
  padding: 10px 0; border-bottom: 1px dotted rgba(26, 22, 20, 0.2);
  display: flex; justify-content: space-between; gap: 16px;
  align-items: baseline;
}
.lineage-item .name {
  font-family: 'Fraunces', 'Noto Serif KR', serif;
  font-weight: 600; font-size: 0.95rem;
}
.lineage-item a { color: inherit; text-decoration: none; border-bottom: 1px dotted currentColor; }
.lineage-item a:hover { color: var(--accent); }
.lineage-item .sig {
  font-family: 'JetBrains Mono', monospace; font-size: 0.68rem;
  color: var(--muted); white-space: nowrap;
}
.lineage-more { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--muted); margin-top: 8px; }

@media (max-width: 820px) {
  .profile-head { grid-template-columns: 1fr; gap: 32px; }
  .phase { grid-template-columns: 1fr; gap: 8px; }
  .phase-meta { display: flex; align-items: baseline; gap: 12px; }
  .lineage-grid { grid-template-columns: 1fr; gap: 24px; }
}

.foot {
  margin-top: 80px; padding-top: 24px;
  border-top: 1px solid var(--ink);
  display: flex; justify-content: space-between;
  flex-wrap: wrap; gap: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem; text-transform: uppercase;
  letter-spacing: 0.12em; color: var(--muted);
}
.foot a { color: var(--muted); }
"""


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;0,9..144,900;1,9..144,400&family=JetBrains+Mono:wght@400;500;700&family=Noto+Serif+KR:wght@300;400;500;600;700;900&family=Pretendard:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>__CSS__</style>
</head>
<body>
<div class="grain"></div>
<div class="container">

  <header class="masthead">
    <div class="brand"><a href="../index.html">Robo <span class="amp">·</span> Careers</a></div>
    <div class="right">
      <span><a class="back-link" href="../index.html" id="backLink">← home</a></span>
      <span><a class="back-link" href="../methodology.html" id="methodologyLink">methodology&nbsp;↗</a></span>
      <span class="lang-tabs">
        <a class="lang-tab" data-lang="en" href="#en">EN</a>
        <span class="lang-sep">/</span>
        <a class="lang-tab" data-lang="ko" href="#ko">KO</a>
      </span>
    </div>
  </header>

  <div class="rank-badge" id="rankBadge"></div>

  <div class="profile-head">
    <div>
      <div class="profile-tag" id="tagEl"></div>
      <h1 class="profile-name" id="nameEl"></h1>
      <p class="profile-oneline" id="oneLineEl"></p>
    </div>
    <dl class="profile-facts" id="factsEl"></dl>
  </div>

  <div class="section" id="venuePlotSection">
    <div class="section-label" id="venuePlotLabel"></div>
    <h3 class="section-title" id="venuePlotTitle"></h3>
    <div class="venue-plot-box">
      <canvas id="venuePlotCanvas"></canvas>
    </div>
    <div class="venue-plot-caption" id="venuePlotCaption"></div>
  </div>

  <div class="section" id="phasesSection">
    <div class="section-label" id="phasesLabel"></div>
    <h3 class="section-title" id="phasesTitle"></h3>
    <div class="phases" id="phasesEl"></div>
  </div>

  <div class="pullquote" id="pullquoteEl"></div>

  <div class="section" id="themesSection">
    <div class="section-label" id="themesLabel"></div>
    <h3 class="section-title" id="themesTitle"></h3>
    <div class="themes" id="themesEl"></div>
  </div>

  <div class="section" id="hlSection">
    <div class="section-label" id="hlLabel"></div>
    <h3 class="section-title" id="hlTitle"></h3>
    <div class="highlights" id="hlEl"></div>
  </div>

  <div class="section" id="lineageSection">
    <div class="section-label" id="lineageLabel"></div>
    <h3 class="section-title" id="lineageTitle"></h3>
    <div class="lineage-grid" id="lineageEl"></div>
  </div>

  <footer class="foot">
    <span id="footData"></span>
    <span><a href="../index.html">← All researchers</a></span>
    <span>Built __DATE__</span>
  </footer>
</div>

<script>
const DATA = __DATA__;
const SLUG_TO_NAME = __SLUG_MAP__;

const I18N = {
  en: {
    venuePlotLabel: "PUBLICATION TIMELINE",
    venuePlotTitle: "Year-by-year output, colored by venue.",
    venuePlotCaption: "Counts are atlas-only (ICRA · IROS · RA-L · T-RO · RSS · IJRR · Sci-Rob · SoRo · T-Mech).",
    phasesLabel: "BY PERIOD",
    phasesTitle: "Career in 5-year windows.",
    themesLabel: "THROUGH-LINES",
    themesTitle: "Themes that cut across all periods.",
    hlLabel: "KEY WORKS",
    hlTitle: "Highly-cited anchor papers within the covered venues.",
    lineageLabel: "LINEAGE",
    lineageTitle: "Mentors and mentees inferred from coauthor patterns.",
    advisorsHeading: "Likely advisor(s)",
    studentsHeading: n => `Likely students (${n})`,
    noAdvisor: "No mentor signal (self-started or sparse early data)",
    noStudent: "No student signal",
    advisorMeta: a => `${a.advisor_active_from}~ · last-author on ${a.advisor_last_author_count}/${a.early_copubs_as_our_first_author} of our early 1st-author`,
    studentMeta: s => `${s.student_first_year}~${s.last_copub_year} · last-author on ${s.we_last_author_count}/${s.student_first_author_count}`,
    moreStudents: n => `+ ${n} more`,
    rankBadge: (rank, natural, composite, archetype, force) => {
      const natPart = (natural && natural !== rank) ? ` · composite rank #${natural}` : '';
      const forcePart = force ? ` · editor's pick (curated for sub-field coverage)` : '';
      return `#${rank}${natPart} · composite ${composite.toFixed(2)} · ${archetype}${forcePart}`;
    },
    citesSuffix: "cites",
    footData: 'Data: <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank">robopaper-atlas</a>',
    home: "← home",
  },
  ko: {
    venuePlotLabel: "출판 타임라인",
    venuePlotTitle: "연도별 출판량, venue 별 색상.",
    venuePlotCaption: "집계는 atlas 9개 venue 내부(ICRA · IROS · RA-L · T-RO · RSS · IJRR · Sci-Rob · SoRo · T-Mech) 기준.",
    phasesLabel: "시기별 궤적",
    phasesTitle: "5년 단위로 본 연구 단계.",
    themesLabel: "관통하는 주제",
    themesTitle: "시기를 가로질러 지속되는 테마.",
    hlLabel: "대표작",
    hlTitle: "해당 학회 기준 고인용 앵커 논문.",
    lineageLabel: "계보",
    lineageTitle: "공저 패턴으로 추정한 멘토와 제자.",
    advisorsHeading: "멘토 후보",
    studentsHeading: n => `제자 후보 (${n})`,
    noAdvisor: "멘토 후보 신호 없음 (자체 시작 또는 데이터 부족)",
    noStudent: "제자 후보 신호 없음",
    advisorMeta: a => `${a.advisor_active_from}~ · 본인 초기 1저자 ${a.early_copubs_as_our_first_author}편 중 멘토 마지막저자 ${a.advisor_last_author_count}편`,
    studentMeta: s => `${s.student_first_year}~${s.last_copub_year} · 본인 마지막저자 ${s.we_last_author_count}편 / 학생 1저자 ${s.student_first_author_count}편 중`,
    moreStudents: n => `+ ${n}명 더`,
    rankBadge: (rank, natural, composite, archetype, force) => {
      const natPart = (natural && natural !== rank) ? ` · 합성점수 순위 #${natural}` : '';
      const forcePart = force ? ` · 편집자 추가 조사 (분야 대표성 확보)` : '';
      return `#${rank}${natPart} · 합성점수 ${composite.toFixed(2)} · ${archetype}${forcePart}`;
    },
    citesSuffix: "회 인용",
    footData: '데이터: <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank">robopaper-atlas</a>',
    home: "← 홈으로",
  }
};

function getLang() {
  const h = window.location.hash.replace('#','').toLowerCase();
  if (h === 'ko' || h === 'kor') return 'ko';
  return 'en';
}
let LANG = getLang();

function setLang(l) {
  LANG = l;
  if (l === 'en') history.replaceState(null, '', window.location.pathname + window.location.search);
  else history.replaceState(null, '', '#' + l);
  document.documentElement.lang = l === 'ko' ? 'ko' : 'en';
  render();
}

function safeLink(name) {
  const slug = SLUG_TO_NAME[name];
  if (!slug) return name;
  return `<a href="${slug}.html${LANG === 'ko' ? '#ko' : ''}">${name}</a>`;
}

function render() {
  const d = DATA[LANG];
  const T = I18N[LANG];
  const meta = DATA.meta;

  document.title = `${meta.name} · Robo · Careers`;
  document.getElementById('rankBadge').textContent = T.rankBadge(meta.rank, meta.natural_rank, meta.composite, d.archetype, meta.force_included);
  document.getElementById('tagEl').textContent = d.tagline;
  document.getElementById('nameEl').innerHTML = `<span class="given">${meta.given}</span><span class="family">${meta.family}</span>`;
  document.getElementById('oneLineEl').innerHTML = d.oneLine;
  document.getElementById('factsEl').innerHTML = d.facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');

  // Venue-year chart (destroy old instance before re-render on lang change)
  if (window._venueChart) { try { window._venueChart.destroy(); } catch(e) {} window._venueChart = null; }
  document.getElementById('venuePlotLabel').textContent = T.venuePlotLabel;
  document.getElementById('venuePlotTitle').textContent = T.venuePlotTitle;
  document.getElementById('venuePlotCaption').textContent = T.venuePlotCaption;
  const vys = d.venue_year_series;
  // Same palette as robopaper-atlas (matplotlib tab10 variant) so the
  // venues read identically across the two sites.
  const VENUE_COLORS = {
    'ICRA':    '#1f77b4',
    'IROS':    '#ff7f0e',
    'RA-L':    '#2ca02c',
    'T-RO':    '#d62728',
    'RSS':     '#9467bd',
    'IJRR':    '#8c564b',
    'Sci-Rob': '#17becf',
    'SoRo':    '#e377c2',
    'T-Mech':  '#bcbd22',
  };
  if (vys && vys.years && vys.years.length) {
    const ctx = document.getElementById('venuePlotCanvas');
    const datasets = vys.venues.map(v => ({
      label: v,
      data: vys.matrix[v],
      borderColor: VENUE_COLORS[v] || '#555',
      backgroundColor: (VENUE_COLORS[v] || '#555') + '22',
      borderWidth: 2,
      tension: 0.25,
      pointRadius: 0,
      pointHoverRadius: 3,
      fill: false,
    }));
    window._venueChart = new Chart(ctx, {
      type: 'line',
      data: { labels: vys.years, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              font: { family: "'JetBrains Mono', monospace", size: 10 },
              color: '#1a1614',
              boxWidth: 10, boxHeight: 10, padding: 8,
            },
          },
          tooltip: {
            callbacks: {
              title: (items) => items[0].label,
              label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}`,
            },
          },
        },
        scales: {
          x: {
            ticks: { font: { size: 9, family: "'JetBrains Mono', monospace" }, color: '#6b6259', maxRotation: 0, autoSkip: true, maxTicksLimit: 12 },
            grid: { display: false },
          },
          y: {
            beginAtZero: true, ticks: { font: { size: 9 }, color: '#6b6259' },
            grid: { color: 'rgba(26,22,20,0.08)' },
          },
        },
      },
    });
  }

  document.getElementById('phasesLabel').textContent = T.phasesLabel;
  document.getElementById('phasesTitle').textContent = T.phasesTitle;
  document.getElementById('phasesEl').innerHTML = d.phases.map(ph => {
    const glossHTML = (ph.glossary && ph.glossary.length)
      ? `<div class="phase-glossary">
           <h5>${LANG === 'ko' ? '용어 설명' : 'Terms'}</h5>
           <ul>${ph.glossary.map(g => `<li><strong>${g.term}</strong> — ${g.gloss}</li>`).join('')}</ul>
         </div>`
      : '';
    return `
    <div class="phase">
      <div class="phase-meta">
        <div class="phase-years">${ph.years}</div>
        <div class="phase-id">${ph.id}</div>
      </div>
      <div class="phase-body">
        <h4>${ph.title}</h4>
        <p>${ph.body}</p>
        ${glossHTML}
      </div>
    </div>`;
  }).join('');

  document.getElementById('pullquoteEl').innerHTML = d.pullquote;

  document.getElementById('themesLabel').textContent = T.themesLabel;
  document.getElementById('themesTitle').textContent = T.themesTitle;
  document.getElementById('themesEl').innerHTML = d.themes.map(t => `
    <div class="theme">
      <div class="theme-num">${t.num}</div>
      <h5>${t.title}</h5>
      <p>${t.text}</p>
    </div>`).join('');

  document.getElementById('hlLabel').textContent = T.hlLabel;
  document.getElementById('hlTitle').textContent = T.hlTitle;
  document.getElementById('hlEl').innerHTML = d.highlights.map(h => `
    <div class="hl-item">
      <span class="hl-year">${h.year}</span>
      <span class="hl-title"><span class="venue">${h.venue}</span>${h.title}</span>
      <span class="hl-cites"><strong>${h.cites.toLocaleString()}</strong> ${T.citesSuffix}</span>
    </div>`).join('');

  document.getElementById('lineageLabel').textContent = T.lineageLabel;
  document.getElementById('lineageTitle').textContent = T.lineageTitle;
  const lg = d.lineage;
  const advHTML = lg.advisors && lg.advisors.length
    ? lg.advisors.map(a => `<div class="lineage-item"><span class="name">${safeLink(a.name)}</span><span class="sig">${T.advisorMeta(a)}</span></div>`).join('')
    : `<div class="sig" style="padding:10px 0;">${T.noAdvisor}</div>`;
  const studHTML = lg.students_shown && lg.students_shown.length
    ? lg.students_shown.map(s => `<div class="lineage-item"><span class="name">${safeLink(s.name)}</span><span class="sig">${T.studentMeta(s)}</span></div>`).join('')
      + (lg.students_rest > 0 ? `<div class="lineage-more">${T.moreStudents(lg.students_rest)}</div>` : '')
    : `<div class="sig" style="padding:10px 0;">${T.noStudent}</div>`;
  document.getElementById('lineageEl').innerHTML = `
    <div class="lineage-block">
      <h5>${T.advisorsHeading}</h5>
      ${advHTML}
    </div>
    <div class="lineage-block">
      <h5>${T.studentsHeading((lg.students || []).length)}</h5>
      ${studHTML}
    </div>`;

  document.getElementById('footData').innerHTML = T.footData;
  document.getElementById('backLink').textContent = T.home;
  const mL = document.getElementById('methodologyLink');
  if (mL) {
    mL.textContent = (LANG === 'ko' ? '방법론 ↗' : 'methodology ↗');
    mL.href = '../methodology.html' + (LANG === 'ko' ? '#ko' : '');
  }
  document.querySelectorAll('.lang-tab').forEach(t => t.classList.toggle('active', t.dataset.lang === LANG));
}

document.querySelectorAll('.lang-tab').forEach(t => {
  t.addEventListener('click', e => { e.preventDefault(); setLang(t.dataset.lang); });
});
window.addEventListener('hashchange', () => {
  const l = getLang();
  if (l !== LANG) { LANG = l; render(); }
});
render();
</script>
</body>
</html>
"""


def main():
    meta, profiles = load_all()
    os.makedirs(OUT_DIR, exist_ok=True)

    # Paper corpus + global IDF for distinctive-phrase extraction
    print("Loading paper corpus for title-phrase extraction...", file=sys.stderr)
    papers = load_papers()
    author_idx = build_author_index(papers)
    idf, max_idf = build_global_idf(papers)
    print(f"  {len(papers):,} papers indexed", file=sys.stderr)

    slug_map = {p["name"]: p["slug"] for p in profiles}
    dynasty_map = {
        x["name"]: x["students_in_topN"]
        for x in meta.get("dynasty_ranking", [])
    }

    today = datetime.date.today().isoformat()

    # Diversity-aware theme usage counters — one per language so picks don't bleed
    usage_en = {}
    usage_ko = {}

    for p in profiles:
        ri = p.get("_rank_info", {})
        toks = p["name"].split()
        given = " ".join(toks[:-1]) if len(toks) > 1 else ""
        family = toks[-1] if toks else p["name"]

        # Resolve this author's papers from raw corpus
        name_idxs = author_idx.get(p["name"], [])
        author_papers = [papers[i] for i in name_idxs]

        en_data = build_page_data(p, author_papers, idf, max_idf, meta, "en", dynasty_map,
                                  usage_counter=usage_en)
        ko_data = build_page_data(p, author_papers, idf, max_idf, meta, "ko", dynasty_map,
                                  usage_counter=usage_ko)

        archetype = dynasty_map  # just reuse; real archetype from meta
        archetype_en = next(
            (a["archetype"] for a in meta["archetype_assignments"] if a["name"] == p["name"]),
            "—",
        )
        # attach archetype to each lang-data
        en_data["archetype"] = archetype_en
        ko_data["archetype"] = archetype_en

        payload = {
            "meta": {
                "name": p["name"],
                "given": given,
                "family": family,
                "slug": p["slug"],
                "rank": ri.get("rank", 0),
                "natural_rank": ri.get("natural_rank", 0),
                "force_included": bool(ri.get("force_included", False)),
                "composite": ri.get("composite", 0),
            },
            "en": en_data,
            "ko": ko_data,
        }

        title = f"{p['name']} · Robo · Careers"
        html = (
            HTML_TEMPLATE
            .replace("__CSS__", CSS)
            .replace("__TITLE__", title)
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False))
            .replace("__SLUG_MAP__", json.dumps(slug_map, ensure_ascii=False))
            .replace("__DATE__", today)
        )
        out = os.path.join(OUT_DIR, f"{p['slug']}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)

    print(f"Wrote {len(profiles)} pages to {OUT_DIR}/", file=sys.stderr)


if __name__ == "__main__":
    main()
