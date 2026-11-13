#!/usr/bin/env python3
"""Enrich grants.json with a `keywords` field for the GrantFinder v2 idea-matcher.

Deterministic and re-runnable: reads grants.json, recomputes keywords from
category + name + org + eligibility + why_easy + funding_text, writes back
in place. Never invents URLs / amounts / deadlines; keywords only.

Usage: python3 enrich.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "grants.json"

CATEGORY_KEYWORDS = {
    "Climate & Environment": ["climate", "carbon", "clean energy", "solar", "wind", "waste",
                              "recycling", "environment", "ocean", "water", "sustainability",
                              "green", "pollution", "energy", "conservation", "biodiversity"],
    "Healthcare & Biotech": ["health", "medical", "pharma", "biotech", "hospital", "patient",
                            "disease", "diagnostic", "drug", "vaccine", "public health",
                            "mental health"],
    "Tech & AI": ["ai", "artificial intelligence", "machine learning", "software", "app",
                  "saas", "platform", "developer", "code", "open source", "data",
                  "robotics", "quantum", "crypto", "blockchain"],
    "Agriculture & Food": ["farm", "agriculture", "food", "crop", "farmer", "agri", "soil",
                           "irrigation", "food security"],
    "Finance & Fintech": ["finance", "fintech", "payment", "banking", "lending",
                          "insurance", "financial inclusion"],
    "Education": ["education", "student", "learning", "school", "edtech", "teaching",
                  "scholarship"],
    "Social Impact": ["social", "poverty", "livelihood", "community", "nonprofit", "ngo",
                      "impact", "women", "youth", "rural", "sanitation"],
    "Gender Equality": ["women", "gender", "girl", "female"],
    "Arts, Culture & Media": ["art", "film", "media", "storytelling", "design", "culture",
                              "music"],
    "Space": ["space", "satellite", "aerospace", "rocket"],
    "Mobility & Transport": ["mobility", "transport", "vehicle", "electric vehicle",
                             "urban", "city"],
    "Housing & Urban": ["housing", "urban", "city", "shelter"],
    "India Government": ["india", "indian", "dpiit", "startup india", "government",
                         "msme", "nidhi", "birac"],
    "Academic Fellowships": ["research", "phd", "masters", "fellowship", "university",
                             "academic", "study"],
    "General / Multi-domain": ["any domain", "open topic", "any sector", "anyone", "general"],
    "Disaster Resilience": ["disaster", "resilience", "relief", "emergency"],
}

# Extra single words / short phrases detected in the free text of an entry.
# These catch cross-domain concepts the category map misses (lab hardware,
# sanitation, tutoring, cold chains, dating, etc.).
EXTRA_VOCAB = [
    # lab / hardware / science
    "lab", "laboratory", "chemistry", "chemical", "device", "hardware",
    "instrument", "prototype", "engineering", "science", "innovation",
    "technology", "medical device", "diagnostic", "pharma", "pharmaceutical",
    "college", "university", "student", "research", "deep tech", "deep-tech",
    "manufacturing", "sensor", "diagnostics",
    # health / sanitation / gender
    "sanitary", "menstrual", "menstruation", "hygiene", "sanitation",
    "girls", "women", "gender", "female", "school", "adolescent",
    # education / learning
    "tutor", "tutoring", "study", "learning", "teacher", "teaching",
    "edtech", "scholarship",
    # agri / energy / food
    "solar", "cold storage", "storage", "farmer", "farming", "agriculture",
    "crop", "food waste", "renewable", "clean energy", "energy",
    "irrigation", "soil", "climate",
    # social / dating / community
    "couples", "dating", "date", "relationship", "community", "youth",
    "rural", "livelihood", "poverty", "nonprofit", "social",
    # tech / startup
    "app", "mobile", "platform", "software", "ai", "machine learning",
    "data", "open source", "startup", "founder", "entrepreneur",
    "business", "market", "india", "indian",
    # finance
    "finance", "fintech", "payment", "banking",
    # misc
    "art", "film", "media", "design", "space", "satellite", "transport",
    "mobility", "housing", "urban", "city", "water", "ocean", "waste",
    "recycling", "environment", "sustainability", "conservation",
]

# Concept bridges: if the text contains the trigger, add the implied keyword.
# E.g. a grant for "sanitation" is also a match for a "sanitary pads" idea.
CONCEPT_BRIDGES = [
    (["sanitation"], ["sanitary", "hygiene"]),
    (["women", "female"], ["girls"]),
    (["school"], ["student", "education"]),
    (["college"], ["student"]),
    (["health"], ["hygiene"]),
    (["food security", "agriculture"], ["farmer"]),
    (["solar"], ["clean energy", "energy"]),
    (["startup"], ["founder"]),
    (["pharma"], ["medical", "health"]),
    (["biotech"], ["health", "medical", "science"]),
    (["diagnostic"], ["medical", "health", "lab"]),
    (["prototype"], ["hardware", "device"]),
    (["hardware"], ["device"]),
    (["robotics"], ["hardware", "engineering"]),
    (["space"], ["aerospace"]),
    (["dating", "couples"], ["relationship", "social"]),
    (["ai"], ["artificial intelligence"]),
]

MAX_KEYWORDS = 12

# Domain base keywords: every grant in a category truthfully shares these
# (an Agriculture grant IS about agriculture even when its one-line entry
# never says the word). Added to every entry in that category. Deliberately
# NOT the full category list — e.g. Tech & AI gets "technology"/"software",
# never "ai": users type "ai" in almost every tech idea, and tagging all 49
# Tech grants "ai" would make them score identically and drown the signal.
CATEGORY_BASE_KEYWORDS = {
    "Climate & Environment": ["climate", "environment", "energy"],
    "Healthcare & Biotech": ["health", "medical"],
    "Tech & AI": ["technology", "software"],
    "Agriculture & Food": ["agriculture", "food", "farmer"],
    "Finance & Fintech": ["finance", "fintech"],
    "Education": ["education", "student"],
    "Social Impact": ["social", "impact"],
    "Gender Equality": ["women", "gender"],
    "Arts, Culture & Media": ["art", "design"],
    "Space": ["space"],
    "Mobility & Transport": ["mobility", "transport"],
    "Housing & Urban": ["housing", "urban"],
    "India Government": ["india", "government"],
    "Academic Fellowships": ["research", "academic"],
    "General / Multi-domain": ["general", "any domain"],
    "Disaster Resilience": ["disaster", "resilience"],
}

# Manual keyword boosts for flagship programmes whose entry text is too terse
# to derive good keywords from (e.g. "BIRAC BIG" says nothing about biotech in
# its one-line entry, yet BIRAC is the Biotechnology Industry Research
# Assistance Council). These are factual, from the programmes' own remits —
# not invented eligibility. Keyed by grant id.
MANUAL_KEYWORDS = {
    "birac-big": ["biotech", "health", "medical", "device", "prototype", "lab",
                  "research", "science", "pharma", "diagnostic", "chemistry"],
    "sine-iit-bombay": ["prototype", "deep tech", "hardware", "device",
                        "innovation", "technology", "research"],
    "nidhi-prayas": ["prototype", "hardware", "device", "innovation", "research",
                   "student"],
    "dsir-prism-promoting-innovations-in-individuals-startups-and-msmes": [
        "prototype", "hardware", "device", "innovation", "research", "student"],
    "startup-india-seed-fund-sisfs": ["prototype", "startup", "innovation"],
    "msme-idea-hackathon": ["prototype", "hardware", "device", "manufacturing"],
    "meity-tide-2-0": ["prototype", "technology", "innovation"],
    "atal-new-india-challenge-anic": ["prototype", "technology", "government"],
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower())


def _contains(text: str, kw: str) -> bool:
    """Word-boundary match (plurals allowed), so 'ai' does not match
    'available', 'art' does not match 'startup', 'app' does not match
    'application'. Hyphens count as spaces."""
    t = text.lower().replace("-", " ")
    words = kw.lower().replace("-", " ").split()
    pat = r"\b" + r"\s+".join(re.escape(w) + r"(?:s|es)?" for w in words) + r"\b"
    return re.search(pat, t) is not None


def keywords_for(g: dict) -> list:
    # NOTE: category/type are deliberately NOT in the match text — the label
    # "Tech & AI" would otherwise match the keyword "ai" for every Tech
    # grant, and "Social Impact" would match "social" for all of them.
    text = " ".join([
        g.get("name", ""), g.get("org", ""), g.get("eligibility", "") or "",
        g.get("why_easy", "") or "", g.get("funding_text", "") or "",
    ]).lower()
    flat = _norm(text)
    padded = f" {flat} "

    out = []

    def add(kw):
        kw = kw.strip().lower()
        if kw and kw not in out:
            out.append(kw)

    # 0. Manual boosts for terse flagship entries (factual, per programme remit).
    for kw in MANUAL_KEYWORDS.get(g.get("id", ""), []):
        add(kw)

    # 0b. Domain base keywords — true of every grant in the category.
    for kw in CATEGORY_BASE_KEYWORDS.get(g.get("category", ""), []):
        add(kw)

    # 1. Category keywords that actually appear in the text (most specific first).
    for kw in CATEGORY_KEYWORDS.get(g.get("category", ""), []):
        if _contains(text, kw):
            add(kw)

    # 2. Extra vocabulary present in the text.
    for kw in EXTRA_VOCAB:
        if _contains(text, kw):
            add(kw)

    # 3. Concept bridges.
    for triggers, implied in CONCEPT_BRIDGES:
        if any(_contains(text, t) for t in triggers):
            for kw in implied:
                add(kw)

    # 4. Stage tags implied by eligibility text.
    elig = (g.get("eligibility", "") or "").lower()
    if any(p in elig for p in ["idea-stage", "idea stage", "no prototype",
                               "no company needed", "no registration required",
                               "not required", "individuals", "anyone"]):
        add("idea-stage")
    if "prototype" in elig or "mvp" in elig.lower():
        add("prototype")
    if "student" in elig:
        add("student")

    # 5. No generic fallback fill: padding terse entries with their whole
    # category list (e.g. every Tech grant getting "ai") wrecks matching by
    # making unrelated grants score identically. Terse entries keep the few
    # keywords their text actually supports; the matcher's open-topic
    # baseline (+2) and name/eligibility scoring still surface them.
    # The one exception: entries with ZERO keywords get the first three
    # keywords of their category, so no entry is unmatchable.
    if not out:
        for kw in CATEGORY_KEYWORDS.get(g.get("category", ""), [])[:3]:
            add(kw)

    # 6. India Government entries are India-relevant by definition.
    if g.get("category") == "India Government":
        add("india")

    return out[:MAX_KEYWORDS]


def main():
    grants = json.loads(DATA.read_text())
    for g in grants:
        g["keywords"] = keywords_for(g)
    DATA.write_text(json.dumps(grants, indent=1, ensure_ascii=False) + "\n")
    empty = [g["name"] for g in grants if not g.get("keywords")]
    print(f"entries: {len(grants)}")
    print(f"entries with empty keywords: {len(empty)} {empty}")
    print(f"avg keywords: {sum(len(g['keywords']) for g in grants) / len(grants):.1f}")
    print(f"max keywords: {max(len(g['keywords']) for g in grants)}")


if __name__ == "__main__":
    main()
