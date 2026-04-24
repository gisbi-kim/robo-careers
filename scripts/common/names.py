"""Name utilities for DBLP authors.

DBLP disambiguates homonyms with a trailing 4-digit id, e.g. 'Tong Qin 0001'.
We strip it for matching/display.
"""
import html as htmllib
import re
import unicodedata

_dblp_tail = re.compile(r"\s+\d{4}$")


def clean_author(s: str) -> str:
    if not s:
        return ""
    return _dblp_tail.sub("", htmllib.unescape(s)).strip()


def split_authors(a_str: str):
    if not a_str:
        return []
    return [clean_author(a) for a in a_str.split(";") if a and a.strip()]


def slugify(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower()
    n = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    return n or "anon"
