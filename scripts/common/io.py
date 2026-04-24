"""Data loaders for robopaper-atlas.

Single entry point: load_papers() -> list[dict] with
    venue, year (int), title, authors (list[str] cleaned), doi, cites, concepts, abstract

Heavy. Call once per script.
"""
import glob
import html as htmllib
import json
import os
import re
from typing import Dict, List

from .names import split_authors

ATLAS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "robopaper-atlas")
)

DBLP_PATH = os.path.join(ATLAS_DIR, "all_dblp.json")
COAUTHOR_PATH = os.path.join(ATLAS_DIR, "coauthor_network.json")

# Front-matter patterns copied from atlas/_clean.py spirit.
_frontmatter = re.compile(
    r"^(table of contents|front matter|editorial|preface|foreword|message from|"
    r"welcome|committee|sponsors|index|author index|keyword index|list of reviewers|"
    r"proceedings|\[.*\])",
    re.IGNORECASE,
)


def is_front_matter(title: str) -> bool:
    if not title:
        return True
    t = title.strip()
    if len(t) < 6:
        return True
    return bool(_frontmatter.match(t))


def load_enriched() -> Dict[str, dict]:
    """Merge all enriched_checkpoint_*.json into {doi: enrichment}."""
    merged: Dict[str, dict] = {}
    for fp in sorted(glob.glob(os.path.join(ATLAS_DIR, "enriched_checkpoint_*.json"))):
        with open(fp, encoding="utf-8") as f:
            merged.update(json.load(f))
    return merged


def load_papers() -> List[dict]:
    """Return merged DBLP+enriched paper list.

    Each record:
        venue: str
        year: int (0 if unknown)
        title: str
        authors: list[str]
        doi: str
        cites: int
        concepts: list[str]
        abstract: str
        dblp_key: str
    """
    with open(DBLP_PATH, encoding="utf-8") as f:
        dblp = json.load(f)
    enriched = load_enriched()
    out = []
    for rec in dblp:
        raw_title = htmllib.unescape((rec.get("title") or "").strip()).rstrip(".").strip()
        if is_front_matter(raw_title):
            continue
        authors = split_authors(rec.get("authors", ""))
        if not authors:
            continue
        try:
            y = int(rec.get("year") or 0)
        except (ValueError, TypeError):
            y = 0
        doi = (rec.get("doi") or "").lower()
        enr = enriched.get(doi, {})
        try:
            cites = int(enr.get("cited_by_count") or 0)
        except (ValueError, TypeError):
            cites = 0
        concepts_raw = enr.get("concepts") or ""
        concepts = [c.strip() for c in concepts_raw.split(";") if c.strip()]
        out.append({
            "venue": (rec.get("venue") or "").strip(),
            "year": y,
            "title": raw_title,
            "authors": authors,
            "doi": doi,
            "cites": cites,
            "concepts": concepts,
            "abstract": enr.get("abstract") or "",
            "dblp_key": rec.get("dblp_key", ""),
        })
    return out


def load_coauthor_network() -> dict:
    with open(COAUTHOR_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_author_index(papers: List[dict]) -> Dict[str, List[int]]:
    """Author -> list of paper indices (into `papers`)."""
    idx: Dict[str, List[int]] = {}
    for i, p in enumerate(papers):
        for a in p["authors"]:
            idx.setdefault(a, []).append(i)
    return idx
