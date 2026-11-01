"""Transparent keyword rules that sort items into the website's topic pages."""

from __future__ import annotations

import re

# Topic key == Jekyll category on dragon28.github.io.
TOPICS = {
    "nano-technology": "Nanotechnology",
    "bio-technology": "Biotechnology",
    "chemical-technology": "Chemical Technology",
    "computer-technology": "Computer Technology",
}

KEYWORDS = {
    "nano-technology": [
        "nano", "graphene", "quantum dot", "2d material", "atomic layer", "nanowire",
        "nanotube", "monolayer", "metasurface", "plasmon",
    ],
    "bio-technology": [
        "gene", "genom", "crispr", "protein", "enzyme", "cell", "microb", "bacteri",
        "vaccine", "antibod", "dna", "rna", "biotech", "tissue", "drug",
    ],
    "chemical-technology": [
        "catalys", "chemical", "chemistry", "molecul", "polymer", "electrolyte",
        "battery", "synthesis", "solvent", "reaction",
    ],
    "computer-technology": [
        "comput", "algorithm", "software", "artificial intelligence", "machine learning",
        "neural network", "robot", "chip", "semiconductor", "quantum computer", "data",
    ],
}


def score(text: str) -> dict[str, int]:
    text = text.lower()
    return {
        topic: sum(len(re.findall(r"\b" + re.escape(w), text)) for w in words)
        for topic, words in KEYWORDS.items()
    }


def classify(title: str, excerpt: str, default: str) -> str:
    """Title matches count double. Ties and no-match fall back to the feed's topic."""
    if default not in TOPICS:
        raise ValueError(f"unknown topic {default!r}")
    t, e = score(title), score(excerpt)
    totals = {k: 2 * t[k] + e[k] for k in TOPICS}
    best = max(totals.values())
    if best == 0:
        return default
    winners = [k for k, v in totals.items() if v == best]
    return default if default in winners else winners[0]
