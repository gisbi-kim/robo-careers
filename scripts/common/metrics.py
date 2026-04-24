"""Bibliometric + trajectory metrics."""
from __future__ import annotations

import collections
import math
from typing import Dict, Iterable, List, Tuple


def h_index(cites: Iterable[int]) -> int:
    s = sorted((c for c in cites if c is not None), reverse=True)
    h = 0
    for i, c in enumerate(s, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def i10_index(cites: Iterable[int]) -> int:
    return sum(1 for c in cites if c is not None and c >= 10)


def seminal_count(cites: Iterable[int], threshold: int = 500) -> int:
    return sum(1 for c in cites if c is not None and c >= threshold)


def z_scores(values: List[float]) -> List[float]:
    if not values:
        return []
    m = sum(values) / len(values)
    var = sum((v - m) ** 2 for v in values) / max(len(values) - 1, 1)
    sd = math.sqrt(var) if var > 0 else 1.0
    return [(v - m) / sd for v in values]


def window_iter(year_start: int, year_end: int, size: int = 5):
    y = year_start
    while y <= year_end:
        yield y, min(y + size - 1, year_end)
        y += size


def concept_vector(papers_in_window) -> Dict[str, float]:
    """Frequency vector of concepts (L1-normalized)."""
    cnt = collections.Counter()
    for p in papers_in_window:
        for c in p.get("concepts") or []:
            cnt[c] += 1
    total = sum(cnt.values()) or 1
    return {k: v / total for k, v in cnt.items()}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def pivot_score(windows: List[Tuple[Tuple[int, int], Dict[str, float]]]) -> float:
    """Mean cosine distance between consecutive 5y windows."""
    if len(windows) < 2:
        return 0.0
    dists = []
    for i in range(1, len(windows)):
        sim = cosine(windows[i - 1][1], windows[i][1])
        dists.append(1 - sim)
    return sum(dists) / len(dists)


def year_series(papers: List[dict], year_start: int, year_end: int) -> Dict[int, dict]:
    """Per-year aggregates for one author's papers."""
    out = {y: {"n": 0, "cites": 0, "max_cites": 0} for y in range(year_start, year_end + 1)}
    for p in papers:
        y = p["year"]
        if year_start <= y <= year_end:
            out[y]["n"] += 1
            out[y]["cites"] += p["cites"]
            out[y]["max_cites"] = max(out[y]["max_cites"], p["cites"])
    return out


def role_guess(author_name: str, paper_authors: List[str]) -> str:
    if not paper_authors:
        return "unknown"
    if paper_authors[0] == author_name:
        return "first"
    if paper_authors[-1] == author_name and len(paper_authors) > 1:
        return "last"
    if len(paper_authors) == 1:
        return "solo"
    return "middle"
