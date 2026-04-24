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
        win_phrases = phrases_for_window(author_papers, win["start"], win["end"], idf, max_idf, k=4)
        phases.append({
            "years": f"{win['start']} — {win['end']}",
            "id": ROMAN[i] if i < len(ROMAN) else str(i + 1),
            "title": phase_title(win, win_phrases, i, total, lang),
            "body": phase_body(profile, win, v, c, win_phrases, i, total, lang),
        })
    return phases


def build_themes(profile, author_papers, idf, max_idf, meta_dynasty, lang):
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

    # Theme 2: team / lab dynamics
    early_n = td.get("early_mean_n_authors")
    late_n = td.get("late_mean_n_authors")
    if early_n and late_n and late_n - early_n > 1.0:
        if lang == "ko":
            themes.append({
                "num": "02",
                "title": "혼자 쓰던 사람에서 랩을 이끄는 사람으로",
                "text": (
                    f"논문당 평균 저자수가 초기 {early_n:.1f}명에서 후기 {late_n:.1f}명으로 1명 이상 늘어났다. "
                    "팀을 꾸리고 처리량을 늘리는 전형적인 PI 전환 궤적이다. "
                    f"공저 패턴으로 추정되는 제자 {len(students)}명이 그 스케일이 실재함을 뒷받침한다. "
                    "박사 후반부나 PI 초반의 단독 연구자가 그룹 리더로 성장한 전형적 경로."
                ),
            })
        else:
            themes.append({
                "num": "02",
                "title": "From solo author to lab head",
                "text": (
                    f"Authors per paper grew from {early_n:.1f} early to {late_n:.1f} late — the canonical PI-scaling arc. "
                    f"{len(students)} likely students underwrite that scale in the coauthor data. "
                    "A textbook progression from individual contributor to group leader."
                ),
            })
    elif early_n and late_n and abs(late_n - early_n) < 0.5 and cs["total_papers"] >= 150:
        if lang == "ko":
            themes.append({
                "num": "02",
                "title": "스케일보다 지속성으로",
                "text": (
                    f"논문당 공저자 수는 초기 {early_n:.1f}명에서 후기 {late_n:.1f}명으로 거의 변동이 없다. "
                    f"팀을 불리는 전략 대신 지속적인 생산성으로 {cs['total_papers']}편이라는 누적을 만들어냈다. "
                    "이 경력의 시그니처는 규모의 확장이 아니라 시간의 복리."
                ),
            })
        else:
            themes.append({
                "num": "02",
                "title": "Duration over scale",
                "text": (
                    f"Coauthor counts barely move — {early_n:.1f} early, {late_n:.1f} late. "
                    f"Instead of scaling a team, sustained productivity delivered {cs['total_papers']} papers. "
                    "The signature here is the compounding of time, not expansion of team size."
                ),
            })
    else:
        if lang == "ko":
            themes.append({
                "num": "02",
                "title": "시간이 누적시킨 것 — 한 편씩",
                "text": (
                    f"{cs['span']}년 동안 총 {cs['total_papers']}편, h={cs['h_index']}. "
                    "소수의 대형 블록버스터도 있지만, 사실 이 h-index를 지탱하는 실체는 "
                    "꾸준하게 중간층을 채우는 생산성이다. "
                    "한 편의 히트가 아니라 긴 복리의 결과로 읽어야 한다."
                ),
            })
        else:
            themes.append({
                "num": "02",
                "title": "What time accumulates, one paper at a time",
                "text": (
                    f"{cs['total_papers']} papers, h={cs['h_index']}, across {cs['span']} years. "
                    "The headline blockbusters matter, but the real engine under the h-index is "
                    "the sustained mid-tier output — a long compounding curve rather than a single hit."
                ),
            })

    # Theme 3: lineage / legacy
    topN_students = meta_dynasty.get(profile["name"], 0)
    if len(students) >= 10 or topN_students >= 1:
        if lang == "ko":
            mentor_part = ""
            if advisors:
                mentor_part = f" 본인은 {advisors[0]['name']}의 네트워크 안에서 경력을 시작한 것으로 보이지만, "
            top_prog = ", ".join(s["name"] for s in students[:4])
            cont_line = (
                f"이 가운데 {topN_students}명은 본 집계 안에 다시 진입해 있다 — 학파 재생산이 진행 중이라는 뜻."
                if topN_students
                else "top 순위 안에 다시 진입한 제자는 아직 없지만, 규모를 감안하면 시간의 문제에 가깝다."
            )
            themes.append({
                "num": "03",
                "title": "논문보다 제자 — 대가의 실체는 사람의 배출",
                "text": (
                    f"{mentor_part}지금은 공저 패턴 기준으로 {len(students)}명 규모의 제자 후보를 거느린 그룹으로 성장했다. "
                    f"대표 이름으로는 {top_prog}이 있다. "
                    f"{cont_line} "
                    "한 연구자가 주어진 분야에 남기는 것 중 가장 오래 가는 유산은, "
                    "결국 자신이 길러낸 또 다른 연구자들이다."
                ),
            })
        else:
            mentor_part = ""
            if advisors:
                mentor_part = f"Launched from {advisors[0]['name']}'s network, "
            top_prog = ", ".join(s["name"] for s in students[:4])
            cont_line = (
                f"{topN_students} of them have re-entered this ranking themselves — dynasty reproduction is already underway."
                if topN_students
                else "None have yet re-entered the ranking, but at this volume it reads like a matter of time."
            )
            themes.append({
                "num": "03",
                "title": "Students as the real record — mastery measured in people",
                "text": (
                    f"{mentor_part}this researcher now sits atop an estimated {len(students)} likely students by coauthor pattern. "
                    f"Names on that list include {top_prog}. "
                    f"{cont_line} "
                    "The longest-lived legacy of any working scientist is, in the end, the other scientists they trained."
                ),
            })
    elif advisors:
        a = advisors[0]
        if lang == "ko":
            themes.append({
                "num": "03",
                "title": f"{a['name']}의 네트워크 안에서 궤도를 잡았다",
                "text": (
                    f"초기 5년 사이 본인이 1저자인 논문 {a['early_copubs_as_our_first_author']}편 중 "
                    f"{a['advisor_last_author_count']}편에 {a['name']}이 마지막저자로 서 있다. "
                    f"박사 과정을 통과하며 경력의 방향을 정한 사람이 {a['name']}이라는 공저 신호다. "
                    "그 이후의 모든 변주도 이 출발점의 영향권 안에서 해석된다."
                ),
            })
        else:
            themes.append({
                "num": "03",
                "title": f"Launched under {a['name']}'s umbrella",
                "text": (
                    f"Of {a['early_copubs_as_our_first_author']} first-author papers in the opening five years, "
                    f"{a['advisor_last_author_count']} carry {a['name']} as last author. "
                    f"The coauthor signal is unmistakable: the direction of this career was set inside {a['name']}'s orbit, "
                    "and every subsequent variation is legible against that origin."
                ),
            })
    else:
        if lang == "ko":
            themes.append({
                "num": "03",
                "title": "자체 궤도 — 학파로 환원되지 않는 경력",
                "text": (
                    "공저 패턴에서 뚜렷한 멘토나 제자 클러스터가 포착되지 않는다. "
                    "초기부터 독립적으로 출판한 유형이거나, 관련 사제 관계가 본 데이터 범위 밖에서 진행되었을 수 있다. "
                    "어느 쪽이든, 이 경력은 학파의 시간표가 아니라 개인의 선택으로 쓰여왔다."
                ),
            })
        else:
            themes.append({
                "num": "03",
                "title": "Own orbit — a career not reducible to a school",
                "text": (
                    "The coauthor-pattern heuristics do not surface a distinct mentor or student cluster. "
                    "Either this researcher operated independently from the start, or the relevant relationships "
                    "sit outside this dataset's coverage. "
                    "Either way, the career here reads as an individual trajectory rather than a school's timetable."
                ),
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


def build_lineage(profile, lang):
    advisors = profile.get("likely_advisors", [])[:3]
    students = profile.get("likely_students", [])
    return {
        "advisors": advisors,
        "students": students,
        "students_shown": students[:12],
        "students_rest": max(len(students) - 12, 0),
    }


def build_page_data(profile, author_papers, idf, max_idf, meta, lang, meta_dynasty):
    archetype_map = {a["name"]: a["archetype"] for a in meta["archetype_assignments"]}
    return {
        "tagline": tagline(profile, lang, author_papers, idf, max_idf),
        "oneLine": one_liner(profile, lang, author_papers, idf, max_idf),
        "facts": build_facts(profile, author_papers, idf, max_idf, archetype_map, lang),
        "phases": build_phases(profile, author_papers, idf, max_idf, lang),
        "themes": build_themes(profile, author_papers, idf, max_idf, meta_dynasty, lang),
        "pullquote": pullquote(profile, lang, author_papers, idf, max_idf),
        "highlights": build_highlights(profile),
        "lineage": build_lineage(profile, lang),
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
      const forcePart = force ? ` · ★ curated (below composite cutoff — included for field coverage)` : '';
      return `#${rank}${natPart} · composite ${composite.toFixed(2)} · ${archetype}${forcePart}`;
    },
    citesSuffix: "cites",
    footData: 'Data: <a href="https://gisbi-kim.github.io/robopaper-atlas/" target="_blank">robopaper-atlas</a>',
    home: "← home",
  },
  ko: {
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
      const forcePart = force ? ` · ★ 큐레이션 포함 (합성점수 기준 컷 아래지만 분야 대표성 확보 위해 포함)` : '';
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

  document.getElementById('phasesLabel').textContent = T.phasesLabel;
  document.getElementById('phasesTitle').textContent = T.phasesTitle;
  document.getElementById('phasesEl').innerHTML = d.phases.map(ph => `
    <div class="phase">
      <div class="phase-meta">
        <div class="phase-years">${ph.years}</div>
        <div class="phase-id">${ph.id}</div>
      </div>
      <div class="phase-body">
        <h4>${ph.title}</h4>
        <p>${ph.body}</p>
      </div>
    </div>`).join('');

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

    for p in profiles:
        ri = p.get("_rank_info", {})
        toks = p["name"].split()
        given = " ".join(toks[:-1]) if len(toks) > 1 else ""
        family = toks[-1] if toks else p["name"]

        # Resolve this author's papers from raw corpus
        name_idxs = author_idx.get(p["name"], [])
        author_papers = [papers[i] for i in name_idxs]

        en_data = build_page_data(p, author_papers, idf, max_idf, meta, "en", dynasty_map)
        ko_data = build_page_data(p, author_papers, idf, max_idf, meta, "ko", dynasty_map)

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
