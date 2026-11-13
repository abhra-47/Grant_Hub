#!/usr/bin/env python3
"""Test harness for the GrantFinder v2 idea-matcher.

Replicates the client-side scoring in index.html EXACTLY (same stopwords,
stemming, synonyms, weights). Run: python3 test_matcher.py
If this file and index.html disagree, index.html is the source of truth and
this file must be updated to match.
"""
import json
import re
from pathlib import Path

DATA = Path(__file__).parent / "grants.json"

STOPWORDS = {
    "a", "an", "the", "for", "and", "to", "of", "in", "on", "with", "my",
    "our", "is", "are", "be", "by", "at", "from", "that", "this", "it",
    "as", "or", "we", "you", "your", "their", "his", "her", "its", "i",
    "am", "an", "if", "so", "but", "not", "no", "do", "does", "will",
    "can", "help", "helps", "helping", "make", "makes", "get", "gets",
    "give", "gives", "one", "two", "new", "more", "all", "any", "per",
    # Generic idea words that match grant boilerplate, not domain fit:
    # "free" matches "free entry", "plan" matches "Business Plan", "young"
    # matches every "young founders" programme, "fun" / "small" / "side"
    # / "stop" / "earn" / "faster" carry no domain signal in this corpus.
    "free", "plan", "small", "young", "fun", "side", "stop", "earn",
    "faster",
}

# Tokens handled ONLY by the dedicated India bonus/penalty, never by
# name/keyword/eligibility scoring — "india" appears in 125/185 grants, so
# letting it score +5 (name) +3 (keyword) +2 (eligibility) would drown every
# domain signal under a +10 India bonus for merely mentioning India.
INDIA_TOKENS = {"india", "indian"}

# Words so generic in programme names ("Co:Lab", "Young Champions",
# "Global Fellowship") that a name hit on them is not a domain signal.
# They still score via keywords / eligibility text.
NAME_GENERIC = {
    "india", "indian", "lab", "youth", "global", "foundation", "fellowship",
    "grant", "prize", "challenge", "program", "programme", "project",
    "fund", "award", "competition", "accelerator", "incubator", "forum",
    "network", "centre", "center", "initiative", "scheme",
    # "Student"/"University" name hits (+5) are near-meaningless in a corpus
    # where a third of programmes are student programmes — they let generic
    # student competitions outrank domain-specific grants. They still score
    # via keywords / eligibility.
    "student", "university", "college", "school",
}

# Idea token -> extra grant-vocabulary tokens to also try matching.
SYNONYMS = {
    "autotitrator": ["lab", "laboratory", "device", "instrument", "chemistry",
                     "diagnostic"],
    "titrator": ["lab", "device", "instrument", "chemistry"],
    "pads": ["sanitary", "menstrual", "hygiene", "sanitation"],
    "pad": ["sanitary", "menstrual", "hygiene", "sanitation"],
    "sanitary": ["menstrual", "hygiene"],
    "menstrual": ["sanitary", "hygiene"],
    "tutor": ["education", "learning", "student", "teaching"],
    "tutoring": ["education", "learning", "student"],
    "tution": ["education"],
    "cold": ["storage", "solar", "energy", "food"],
    "farmer": ["agriculture", "farm", "food", "rural"],
    "farmers": ["agriculture", "farm", "food", "rural"],
    "dating": ["couples", "relationship", "date"],
    "dates": ["couples", "relationship", "date"],
    "couples": ["dating", "relationship", "date"],
    "couple": ["dating", "relationship", "date"],
    # Kept to ONE bridge word each: expanding "college" into student +
    # university + education let one idea word score three times and let
    # generic student competitions outrank domain-specific grants.
    "school": ["student"],
    "college": ["student"],
    "girls": ["women", "gender", "school"],
    "girl": ["women", "gender", "school"],
    "app": ["software", "platform", "mobile"],
    "ai": ["artificial", "intelligence", "machine", "learning"],
    "solar": ["clean", "energy", "renewable", "climate"],
    "affordable": ["low", "cost", "cheap"],
    "cheap": ["low", "cost", "affordable"],
}


def stem(w: str) -> str:
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("es"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def tokenize(text: str) -> list:
    words = re.findall(r"[a-z0-9]+", text.lower())
    out = []
    for w in words:
        if w in STOPWORDS:
            continue
        s = stem(w)
        if s and s not in out:
            out.append(s)
        for syn in SYNONYMS.get(w, []):
            ss = stem(syn)
            if ss and ss not in out:
                out.append(ss)
    return out


def stage_fits(g: dict, stage: str) -> int:
    """Stage fit, in bonus points (not just bool): exact stage = +2, adjacent
    early stage = +1 (an idea-stage founder can still eye a prototype grant
    as their next step, and vice versa). Checks eligibility + funding text.
    Revenue stage: no bonus, no penalty."""
    text = ((g.get("eligibility") or "") + " "
            + (g.get("funding_text") or "")).lower()
    kws = [k.lower() for k in g.get("keywords", [])]
    ideaish = "idea-stage" in kws or "idea" in text or "no prototype" in text
    protoish = "prototype" in kws or "prototype" in text or "mvp" in text
    if stage == "idea":
        if ideaish:
            return 2
        if protoish:
            return 1
        return 0
    if stage in ("prototype", "mvp"):
        if protoish:
            return 2
        if ideaish:
            return 1
        return 0
    return 0


def is_open_topic(g: dict) -> bool:
    elig = (g.get("eligibility") or "").lower()
    return (g.get("category") == "General / Multi-domain"
            or "any domain" in elig or "anyone" in elig
            or "any sector" in elig)


def score(g: dict, tokens: list, stage: str, india_on: bool,
          mentions_india: bool) -> tuple:
    name_words = {stem(w) for w in re.findall(r"[a-z0-9]+", g["name"].lower())}
    elig_words = {stem(w) for w in
                  re.findall(r"[a-z0-9]+", (g.get("eligibility") or "").lower())}
    kw_stems = set()
    for kw in g.get("keywords", []):
        for w in re.findall(r"[a-z0-9]+", kw.lower()):
            kw_stems.add(stem(w))
        kw_stems.add(stem(kw.lower().replace(" ", "")) if " " not in kw else "")

    s = 0
    matched = []
    for t in tokens:
        if t in INDIA_TOKENS:
            continue  # handled by the dedicated India bonus/penalty below
        hit = False
        if t not in NAME_GENERIC and t in name_words:
            s += 5
            hit = True
        if t in kw_stems:
            s += 3
            hit = True
        if t in elig_words:
            s += 2
            hit = True
        if hit:
            matched.append(t)
    if is_open_topic(g):
        s += 2
    if india_on or mentions_india:
        if g.get("india_eligible") is True:
            s += 2
        elif g.get("india_eligible") is False:
            s -= 5
    if stage:
        s += stage_fits(g, stage)
    if g.get("is_hidden_gem") or g.get("is_top_pick"):
        s += 1
    return s, matched


def match(idea: str, stage: str = "idea", india_on: bool = True):
    grants = json.loads(DATA.read_text())
    tokens = tokenize(idea)
    mentions_india = "india" in tokens or "indian" in tokens
    scored = []
    for g in grants:
        s, matched = score(g, tokens, stage, india_on, mentions_india)
        scored.append((s, g, matched))
    max_score = max(s for s, _, _ in scored)
    if max_score <= 0:
        # Fallback: general grants sorted by amount.
        gen = [g for g in grants if is_open_topic(g)]
        gen.sort(key=lambda g: g.get("funding_amount_usd") or -1, reverse=True)
        return tokens, 0, [(0, g, []) for g in gen[:12]]
    scored.sort(key=lambda x: (x[0], x[1].get("funding_amount_usd") or -1),
                reverse=True)
    out = []
    for s, g, matched in scored:
        if s <= 0:
            continue
        pct = round(100 * s / max_score)
        out.append((s, pct, g, matched))
    return tokens, max_score, out


EXAMPLES = [
    ("Affordable autotitrator for college and pharma QC labs in India",
     "idea"),
    ("Free sanitary pads for school girls in India, funded by ads on the pack",
     "idea"),
    ("AI tutor app that helps Indian students study faster and earn on the side",
     "idea"),
    ("Low-cost solar cold storage for small farmers to stop food waste",
     "idea"),
    ("App that helps young couples plan cheap, fun dates in their city",
     "idea"),
]


def main():
    for idea, stage in EXAMPLES:
        tokens, max_score, results = match(idea, stage)
        print(f"\n=== {idea!r}")
        print(f"tokens: {tokens}  maxScore: {max_score}  matches: {len(results)}")
        for s, pct, g, matched in results[:3]:
            print(f"  {pct}% (score {s}) {g['name']} [{g['category']}] "
                  f"{g['funding_text']} matched={matched}")


if __name__ == "__main__":
    main()
