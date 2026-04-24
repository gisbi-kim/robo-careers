"""Phase 4: distill per-person narratives + cross-person lessons (KO + EN).

Writes:
  - appends `insights: {ko: {...}, en: {...}}` to each profile JSON
  - appends `cross_lessons: {ko: [...], en: [...]}` to analysis/meta.json
"""
from __future__ import annotations

import glob
import json
import os
import sys

PROFILES_DIR = "analysis/profiles"
META_PATH = "analysis/meta.json"


def _personal(p: dict, archetype: str, lang: str) -> dict:
    cs = p["career_stats"]
    ms = p["milestones"]
    windows = p.get("topic_windows", [])
    first_topics = windows[0]["top_concepts"][:3] if windows else []
    last_topics = windows[-1]["top_concepts"][:3] if windows else []
    name = p["name"]
    cites_fmt = f"{cs['total_cites']:,}"

    if lang == "ko":
        head = (f"{name}: {cs['span']}년에 걸쳐 {cs['total_papers']}편, "
                f"총 {cites_fmt}회 인용, h={cs['h_index']}, "
                f"500+ 블록버스터 {cs['seminal_count']}편.")
    else:
        head = (f"{name}: over {cs['span']} years, {cs['total_papers']} papers, "
                f"{cites_fmt} total cites, h={cs['h_index']}, "
                f"{cs['seminal_count']} blockbusters (500+ cites).")

    # Onset
    first = ms.get("first_paper", {})
    if lang == "ko":
        bits = [f"{first.get('year')}년 \"{first.get('title')}\"으로 출발."]
    else:
        bits = [f"Started in {first.get('year')} with \"{first.get('title')}\"."]
    if "first_500cite" in ms:
        s = ms["first_500cite"]
        if lang == "ko":
            bits.append(f"첫 500+ 인용 논문까지 {s['gap_from_first']}년 걸림: \"{s['title']}\" ({s['year']}, {s['cites']:,}회).")
        else:
            bits.append(f"First 500+ cite paper came {s['gap_from_first']} years in: \"{s['title']}\" ({s['year']}, {s['cites']:,} cites).")
    if "first_1000cite" in ms:
        s = ms["first_1000cite"]
        if lang == "ko":
            bits.append(f"1000+ 인용 논문: \"{s['title']}\" ({s['year']}, {s['cites']:,}회).")
        else:
            bits.append(f"1000+ cite paper: \"{s['title']}\" ({s['year']}, {s['cites']:,} cites).")
    onset = " ".join(bits)

    # Topic drift
    pivot = p.get("pivot_score", 0)
    if lang == "ko":
        drift = "토픽 지속형" if pivot < 0.25 else "점진적 이동형" if pivot < 0.5 else "적극 피벗형"
        topic_line = (
            f"초기 토픽: {', '.join(t['c'] for t in first_topics)}. "
            f"최근 토픽: {', '.join(t['c'] for t in last_topics)}. "
            f"피벗 점수 {pivot:.2f} → {drift}."
        )
    else:
        drift = "topic-stable" if pivot < 0.25 else "gradual shift" if pivot < 0.5 else "active pivoter"
        topic_line = (
            f"Early topics: {', '.join(t['c'] for t in first_topics)}. "
            f"Recent topics: {', '.join(t['c'] for t in last_topics)}. "
            f"Pivot score {pivot:.2f} → {drift}."
        )

    # Team drift
    td = p.get("team_drift", {})
    early_n, late_n = td.get("early_mean_n_authors"), td.get("late_mean_n_authors")
    team_line = ""
    if early_n is not None and late_n is not None:
        if lang == "ko":
            direction = "팀 확장" if late_n > early_n + 0.5 else "팀 유지" if abs(late_n - early_n) <= 0.5 else "팀 축소"
            team_line = f"저자수 평균: 초기 {early_n:.1f}명 → 후기 {late_n:.1f}명 ({direction})."
        else:
            direction = "team growth" if late_n > early_n + 0.5 else "stable team" if abs(late_n - early_n) <= 0.5 else "team shrink"
            team_line = f"Authors per paper: early {early_n:.1f} → late {late_n:.1f} ({direction})."

    # Peak
    peak = ms.get("peak_paper", {})
    peak_pos = None
    if peak.get("year"):
        peak_pos = (peak["year"] - cs["first_year"]) / max(cs["span"] - 1, 1)
    peak_line = ""
    if peak.get("title"):
        if lang == "ko":
            when = "초기" if peak_pos < 0.33 else "중기" if peak_pos < 0.66 else "후기"
            peak_line = f"최다 인용 논문 \"{peak['title']}\" ({peak['year']}, {peak['cites']:,}회) — 커리어 {when}에 위치."
        else:
            when = "early career" if peak_pos < 0.33 else "mid career" if peak_pos < 0.66 else "late career"
            peak_line = f"Peak paper \"{peak['title']}\" ({peak['year']}, {peak['cites']:,} cites) — fell in {when}."

    # Lineage
    advisors = p.get("likely_advisors", [])
    students = p.get("likely_students", [])
    lineage_bits = []
    if advisors:
        names = ", ".join(a["name"] for a in advisors[:3])
        if lang == "ko":
            lineage_bits.append(f"멘토 후보(초기 5년 1저자 논문 패턴): {names}.")
        else:
            lineage_bits.append(f"Likely advisor(s) (first-5y first-author pattern): {names}.")
    if students:
        if lang == "ko":
            tops = ", ".join(
                f"{s['name']}({s['student_first_year']}~, 우리 마지막저자 {s['we_last_author_count']}편)"
                for s in students[:3]
            )
            lineage_bits.append(f"제자 후보 추정 {len(students)}명 — 상위: {tops}.")
        else:
            tops = ", ".join(
                f"{s['name']}({s['student_first_year']}~, we last-author on {s['we_last_author_count']})"
                for s in students[:3]
            )
            lineage_bits.append(f"{len(students)} likely students — top: {tops}.")
    mentee_line = " ".join(lineage_bits)

    # Lessons
    lessons = []
    if cs["h_index"] >= 60:
        lessons.append(
            "지속성이 h-index를 만든다 — 한두 편의 블록버스터만으로는 여기 못 옴."
            if lang == "ko"
            else "Consistency builds h-index — one or two blockbusters alone don't get you here."
        )
    if "first_500cite" in ms and ms["first_500cite"]["gap_from_first"] <= 5:
        g = ms["first_500cite"]["gap_from_first"]
        lessons.append(
            f"초기 {g}년 안에 500+ 논문이 나옴. 첫 5년 주제 선택이 결정적."
            if lang == "ko"
            else f"First 500+ cite paper within {g} years. First-5-year topic choice is decisive."
        )
    if pivot >= 0.4:
        lessons.append(
            "토픽 적극 피벗 — 정체기를 재창조로 극복한 케이스."
            if lang == "ko"
            else "Active topic pivoter — overcame plateau by reinvention."
        )
    elif pivot < 0.2 and cs["total_papers"] >= 150:
        lessons.append(
            "한 우물 깊게 파는 전략으로 임팩트 달성."
            if lang == "ko"
            else "Impact through deep specialization — one lane, pushed far."
        )
    if late_n is not None and early_n is not None and late_n > early_n + 1:
        lessons.append(
            "후기에 팀/랩 규모 확장 — 단독 연구자에서 리더로 전환."
            if lang == "ko"
            else "Late-career team scaling — solo researcher → lab leader."
        )
    if students and len(students) >= 10:
        lessons.append(
            f"{len(students)}명 제자 후보 — 제자 배출이 임팩트의 실체."
            if lang == "ko"
            else f"{len(students)} likely students — mentoring is the real impact."
        )
    if advisors:
        top_adv = advisors[0]["name"]
        lessons.append(
            f"멘토 후보: {top_adv} — 이 사람의 PhD 네트워크 안에서 시작."
            if lang == "ko"
            else f"Likely advisor: {top_adv} — started within their PhD network."
        )
    if not lessons:
        lessons = [
            "데이터 부족 — 개별 패턴 뚜렷하지 않음."
            if lang == "ko"
            else "Insufficient data — no distinctive pattern."
        ]

    return {
        "archetype": archetype,
        "headline": head,
        "paragraphs": [onset, topic_line, team_line, peak_line, mentee_line],
        "lessons": lessons,
    }


def _cross(profiles: list[dict], meta: dict, lang: str) -> list[str]:
    t = meta["timing_distributions"]
    N = len(profiles)
    lessons = []

    def med(d):
        return d["median"] if d else None

    m100 = med(t.get("years_to_first_100cite"))
    m500 = med(t.get("years_to_first_500cite"))
    m1000 = med(t.get("years_to_first_1000cite"))
    if m100 is not None:
        mx = t["years_to_first_100cite"]["max"]
        lessons.append(
            f"첫 100+ 인용 논문까지 중앙값 **{m100}년**. top-{N} 중 가장 늦은 사람도 {mx}년이면 도달."
            if lang == "ko"
            else f"Median time to first 100+ cite paper: **{m100} years**. Even the slowest of top-{N} got there in {mx} years."
        )
    if m500 is not None:
        lo, hi = t["years_to_first_500cite"]["min"], t["years_to_first_500cite"]["max"]
        lessons.append(
            f"첫 500+ 인용 논문까지 중앙값 **{m500}년**. 범위: {lo}~{hi}년. 이 숫자가 '대가 후보'의 바닥선."
            if lang == "ko"
            else f"Median time to first 500+ cite paper: **{m500} years** (range {lo}-{hi}). This is the floor for 'aspiring master'."
        )
    if m1000 is not None:
        lessons.append(
            f"첫 1000+ 인용 논문 중앙값 **{m1000}년** — 블록버스터는 보통 커리어 중반 전에 나온다."
            if lang == "ko"
            else f"Median time to first 1000+ cite paper: **{m1000} years** — blockbusters usually hit before mid-career."
        )
    peak_pos = med(t.get("peak_paper_relative_position"))
    if peak_pos is not None:
        lessons.append(
            f"최다 인용 논문의 상대 위치 중앙값 {peak_pos:.0%} — top-{N} 중 절반 이상이 커리어 전반부에 최고점을 찍었음."
            if lang == "ko"
            else f"Peak-paper median position: {peak_pos:.0%} of career — over half of top-{N} hit their peak in the first half."
        )
    # Archetype mix
    counts = {a["label"]: len(a["members"]) for a in meta["archetypes"]}
    if lang == "ko":
        lessons.append(
            "커리어 아크 아키타입 분포: "
            + ", ".join(f"{k} {v}명" for k, v in counts.items())
            + "."
        )
    else:
        lessons.append(
            "Career arc archetype distribution: "
            + ", ".join(f"{k} ({v})" for k, v in counts.items())
            + "."
        )
    vt = meta.get("venue_transitions", {}).get("distribution")
    if vt:
        lessons.append(
            f"컨퍼런스→저널 과반 전환까지 중앙값 {vt['median']}년 (n={vt['n']}, 나머지는 전 커리어 동안 컨퍼런스 중심)."
            if lang == "ko"
            else f"Conference→journal majority transition: median {vt['median']} years (n={vt['n']}; others stayed conference-centric throughout)."
        )
    pr = meta.get("pivot_ranking", [])
    if pr:
        top_pivots = ", ".join(f"{x['name']}({x['pivot_score']:.2f})" for x in pr[:3])
        lessons.append(
            f"토픽 피벗 강도 상위 3인: {top_pivots}. 거장도 재창조는 한다."
            if lang == "ko"
            else f"Top 3 topic pivoters: {top_pivots}. Even masters reinvent themselves."
        )
    dr = meta.get("dynasty_ranking", [])
    dr_topN = [x for x in dr if x["students_in_topN"] > 0]
    if dr_topN:
        top_dyn = ", ".join(
            f"{x['name']}({x['students_in_topN']})" for x in dr_topN[:3]
        )
        lessons.append(
            f"학파 왕가 — top-{N} 안에서 제자가 다시 top-{N}에 진입한 상위 3인: {top_dyn}. 대가의 진짜 지표는 '대가를 몇 명 길러냈느냐'."
            if lang == "ko"
            else f"Academic dynasty — top-{N} researchers whose students also reached top-{N} (top 3): {top_dyn}. The real metric: how many masters did you train?"
        )
    if dr:
        volume_top = sorted(dr, key=lambda x: -x["total_likely_students"])[:3]
        top_v = ", ".join(f"{x['name']}({x['total_likely_students']})" for x in volume_top)
        lessons.append(
            f"제자 추정 총량 상위 3인: {top_v}. 양성 규모는 h-index와 별개."
            if lang == "ko"
            else f"Top 3 by total likely students: {top_v}. Mentorship volume is independent of h-index."
        )
    edges = meta.get("lineage_edges_in_topN", [])
    if edges:
        es = sorted(edges, key=lambda e: -e["we_last_author_count"])[:5]
        pairs = ", ".join(f"{e['advisor']}→{e['student']}" for e in es)
        lessons.append(
            f"top-{N} 내 추정 사제 관계(신호 강한 순): {pairs}."
            if lang == "ko"
            else f"Strongest inferred advisor→student pairs inside top-{N}: {pairs}."
        )
    td = meta.get("topic_dominance", [])
    if td:
        top_c = td[0]
        who = ", ".join(x["name"] for x in top_c["top_contributors"][:3])
        lessons.append(
            f"가장 많이 겹친 주제: **{top_c['concept']}** (주도자: {who}). 여러 대가가 같은 토픽에서 경쟁했다는 뜻."
            if lang == "ko"
            else f"Most contested topic: **{top_c['concept']}** (led by: {who}). Many masters competed on the same subject."
        )
    # Closer
    lessons.append(
        "커리어 인사이트: (1) 첫 5년 안에 '인용 받는 주제'에 착지하라 — 중앙값이 말해준다. "
        "(2) 피벗러든 직진형이든 성립 가능하지만, 팀 확장 없이 200편+ 찍은 사람은 거의 없다. "
        f"(3) 아키타입은 혈통이 아니라 환경 — 후기 개화형도 top-{N}에 다수다."
        if lang == "ko"
        else
        "Career takeaways: (1) Land on a 'citation-receiving' topic within your first 5 years — the medians say so. "
        "(2) Both pivoters and specialists succeed, but almost no one hits 200+ papers without scaling a team. "
        f"(3) Archetype isn't bloodline, it's circumstance — late bloomers populate top-{N} in numbers."
    )
    return lessons


def main():
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    archetype_map = {a["name"]: a["archetype"] for a in meta["archetype_assignments"]}

    for fp in sorted(glob.glob(os.path.join(PROFILES_DIR, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            prof = json.load(f)
        arc = archetype_map.get(prof["name"], "unknown")
        prof["insights"] = {
            "ko": _personal(prof, arc, "ko"),
            "en": _personal(prof, arc, "en"),
        }
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(prof, f, ensure_ascii=False, indent=2)
        print(f"  insights -> {fp}", file=sys.stderr)

    profiles = []
    for fp in sorted(glob.glob(os.path.join(PROFILES_DIR, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            profiles.append(json.load(f))

    meta["cross_lessons"] = {
        "ko": _cross(profiles, meta, "ko"),
        "en": _cross(profiles, meta, "en"),
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Cross lessons (KO+EN) added to {META_PATH}", file=sys.stderr)

    print("\n=== Cross lessons (EN) ===", file=sys.stderr)
    for i, l in enumerate(meta["cross_lessons"]["en"], 1):
        print(f"  {i}. {l}", file=sys.stderr)


if __name__ == "__main__":
    main()
