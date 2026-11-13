# GrantFinder v2 — Describe your idea. Get your grants.

A static, no-build website that turns Abhrajyoti's funding research into an
**idea-matcher**: type your startup idea in plain words and it scores all
**185 programmes** (grants, fellowships, accelerators, prizes, competitions,
scholarships, credits) against it — no sign-up, no server, matching runs
entirely in your browser. Below the matcher, the full directory from v1 is
kept: search, category / type / deadline / funding-size filters, an
India-eligible toggle, a Hidden Gems toggle, sorting, a Closing-soon strip,
card details in a modal, and an "Add a grant" form that generates a JSON
snippet.

## Files

| File | What it is |
|---|---|
| `index.html` | Single-file app (vanilla JS + Tailwind via CDN). Loads `grants.json` with `fetch()`. No external API calls. Contains the matcher + the browse directory. |
| `grants.json` | Structured data — one entry per programme, each with a `keywords` array (see below). |
| `build.py` | Parser that generated `grants.json` from the two research files. Re-run it after editing the sources: `python3 build.py`. **Note:** re-running `build.py` regenerates entries *without* keywords — run `python3 enrich.py` after it. |
| `enrich.py` | Deterministic keyword generator: recomputes `keywords` for all 185 entries from category + name + org + eligibility + why_easy + funding_text. Re-runnable: `python3 enrich.py`. |
| `test_matcher.py` | Python replica of the client-side matcher (same stopwords, stemming, synonyms, weights). Runs the 5 example ideas and prints top-3 matches: `python3 test_matcher.py`. If this and `index.html` ever disagree, `index.html` is the source of truth and this file must be updated to match. |
| `README.md` | This file. |

## How the idea-matcher works (v2)

1. **Tokenize** the idea: lowercase, split into words, drop stopwords
   (`a, the, for, …` plus junk words that only match grant boilerplate —
   `free` matches "free entry", `plan` matches "Business Plan", `young`
   matches every "young founders" programme), light stemming
   (`farmers → farmer`, `labs → lab`).
2. **Synonym expansion** for words the database never uses: `autotitrator →
   lab, device, diagnostic`; `pads → sanitary, menstrual, hygiene`;
   `tutor → education, student`; `solar → clean, energy, renewable,
   climate`; `college / school → student`; `dating → couples, relationship`.
3. **Score each programme:**
   - **+5** word matches a word in the programme name
   - **+3** word matches a programme keyword
   - **+2** word appears in its eligibility text
   - **+2** India bonus if India-based and the programme is India-eligible;
     **−5** if explicitly not India-eligible
   - **+2** stage fits exactly (idea-stage idea → idea-stage grant;
     prototype → prototype grant); **+1** for the adjacent early stage
     (an idea-stage founder eyeing a prototype grant)
   - **+2** baseline for open-topic programmes (any domain / anyone / any
     sector), so a vague idea still returns something
   - **+1** tie-breaker for Hidden Gems and Top Picks
   - Match % = score ÷ best score in this run × 100. **≥70% Strong match ·
     40–69% Good match · &lt;40% Worth a look.**
   - If the best score is **&lt; 12**, a "No exact domain match?" note shows
     with the top 3 open-topic grants. If nothing scores at all, open-topic
     programmes sorted by amount are shown instead.
4. **Two deliberate guards** (both learned the hard way while testing):
   - "india"/"indian" never score via name/keywords/eligibility — the word
     appears in 125/185 entries, so it would add up to +10 for merely
     mentioning India and drown every domain signal. The India bonus/penalty
     handles it instead.
   - Generic name words (`lab, student, university, fellowship, challenge,
     …`) don't earn the +5 name bonus — "Co:Lab" is a brand, not a
     laboratory, and a third of the database is student programmes.

### Keywords — how they are made

`enrich.py` builds each entry's `keywords` (max 12, lowercase, deduped)
from, in order: (0) a small manual-boost table for flagship programmes
whose one-line entries are too terse to derive from (e.g. BIRAC BIG gets
`biotech, health, medical, device, prototype, lab, pharma, diagnostic,
chemistry` — BIRAC is the Biotechnology Industry Research Assistance
Council; NIDHI-PRAYAS gets `student` — it funds student innovators);
(0b) **domain base keywords**, true of every grant in that category
(e.g. every Agriculture grant gets `agriculture, food, farmer`; every
Tech grant gets `technology, software` — never `ai`, or all 49 Tech grants
would score identically on every AI idea); (1) category keywords that
actually appear in the entry text; (2) an extra cross-domain vocabulary
(lab, hardware, sanitary, solar, couples, …); (3) concept bridges
(`sanitation → sanitary, hygiene`; `women → girls`); (4) stage tags
(`idea-stage`, `prototype`, `student`) implied by the eligibility text.
Matching is word-boundary based, so `ai` never matches "available" and
`art` never matches "startup".

### Test ideas — expected top matches (verified 2026-11-13)

Run `python3 test_matcher.py` — it must print these. If a top-3 changes
after an edit, check whether the change is a genuine improvement before
keeping it.

| Idea | Top 3 |
|---|---|
| Affordable autotitrator for college and pharma QC labs in India | 1. BIRAC BIG 100% · 2. DSIR-PRISM 74% · 3. SINE IIT Bombay 68% (NIDHI-PRAYAS #6, MSME Hackathon #4) |
| Free sanitary pads for school girls in India, funded by ads on the pack | 1. TiE Women 100% · 2. Equalizer Challenge (women's health) 100% · 3. NSRCEL (Women Startup Programme) 100% |
| AI tutor app that helps Indian students study faster and earn on the side | 1. Devpost 100% · 2. Google.org AI grants 100% · 3. AI Safety Camp 95% |
| Low-cost solar cold storage for small farmers to stop food waste | 1. Seeding The Future Global Food System Challenge 100% · 2. Ashden Awards 88% · 3. Thought For Food Challenge 88% |
| App that helps young couples plan cheap, fun dates in their city | Best score 10/… — **no dating-specific grant exists** in the database, so the low-score note triggers and generic tech/open-topic grants surface (Nagarathna Memorial Grant, Devpost, Colosseum). Honest behaviour, not a bug. |

## Data — where it came from

Seed data is Abhrajyoti's research, both files researched **2026-09-25**:

- `~/workspace/your_files/funding-research/global-fellowships-grants-young-founders.md`
  (350 lines, 15 domains, Top Picks 1–16)
- `~/workspace/your_files/funding-research/hidden-gems-easy-grants-young-founders.md`
  (553 lines, hidden gems / low-competition)

Counts in the current build: **185 entries** · **16 Top Picks** · **10 Quick Wins** ·
**70 hidden gems** · **127 India-eligible**, 56 India-eligibility unknown, 2 explicitly
not India-eligible (1517 Medici Project — North America only; EIT Urban Mobility —
EU/Horizon countries only).

### ⚠️ Data freshness warning — read this before applying

- Researched **2026-09-25**. Many 2026 annual cycles closed Feb–Sep 2026; 2027
  cycles were mostly unannounced at research time.
- Many deadlines are marked `unverified` in the data. **Always verify amount,
  eligibility and deadline on the official site before applying.**
- **No URLs, amounts or deadlines were invented.** Where the research files had
  no URL, the entry has `url: null` and the site shows
  "URL unverified — search name". 24 of 185 entries have no URL.
- `funding_amount_usd` is an *approximate* conversion for sorting / bucketing
  only (₹ ÷ 88, £ × 1.34, € × 1.17, SGD × 0.78, CAD × 0.73). The verbatim
  `funding_text` on each card is the source of truth. 49 entries have no
  parseable amount (`funding_amount_usd: null`) — e.g. "Fully funded",
  "No cash — recognition", salary ranges that were not parsed as a single figure.

## `grants.json` schema (one entry)

```json
{
  "id": "thiel-fellowship",
  "name": "Thiel Fellowship",
  "org": "Thiel Foundation",
  "category": "Tech & AI",
  "type": "Fellowship",
  "funding_text": "$250K equity-free over 2 yrs",
  "funding_amount_usd": 250000,
  "funding_currency": "USD",
  "eligibility": "Age ≤22, no university degree (enrolled students must drop out), worldwide",
  "deadline_text": "Rolling, year-round",
  "deadline_status": "rolling",
  "india_eligible": true,
  "url": "https://thielfellowship.org",
  "why_easy": null,
  "is_hidden_gem": false,
  "is_top_pick": true,
  "is_quick_win": false,
  "keywords": ["ai", "university", "student", "artificial intelligence",
               "machine learning", "software"],
  "source_file": "global-fellowships-grants-young-founders.md"
}
```

- `category` — one of: Academic Fellowships, Agriculture & Food, Arts, Culture & Media,
  Climate & Environment, Disaster Resilience, Education, Finance & Fintech,
  Gender Equality, General / Multi-domain, Healthcare & Biotech, Housing & Urban,
  India Government, Mobility & Transport, Social Impact, Space, Tech & AI.
  (Categories are derived from the data at runtime — the filter dropdown and chips
  are built from whatever categories are actually in `grants.json`.)
- `type` — Grant / Fellowship / Accelerator / Prize / Competition / Scholarship / Credits.
- `deadline_status` — `rolling` / `open-now` / `dated` / `unverified` / `closed`.
- `india_eligible` — `true` / `false` / `"unknown"`.
- `funding_amount_usd` — approximate, or `null` if not parseable.
- `keywords` — lowercase tags (max 12) used only by the idea-matcher.
  Generated by `enrich.py`; see "How the idea-matcher works" above.
  Never hand-edit the whole file's keywords — edit `enrich.py` (category
  map / vocab / manual boosts) and re-run it.
- Funding-size buckets in the UI: Micro < $5k · Small $5k–$25k · Mid $25k–$100k ·
  Large $100k+ · Amount not parsed.

## Data corrections made in v2 (2026-11-13)

Four `india_eligible` values were wrong in the v1 data and were fixed in
`grants.json` (the research files' own eligibility text contradicts them):

- **Halcyon thematic intensives** `unknown` → `false` — "Region-locked
  (Africa / Mexico / MENA) … INELIGIBLE for India". (It was ranking #1 for
  a solar cold-storage idea before this fix.)
- **Microsoft AI for Good** `true` → `false` — "$5M Open Call was
  Washington-state only; UK accelerator UK-only; not India-open".
- **NIDHI-PRAYAS** `unknown` → `true` and **Karnataka ELEVATE** `unknown` →
  `true` — both are Indian government schemes (all 8 India Government
  entries are now `true`).

## How to add a grant

1. On the site, use **"Add a grant"** at the bottom — fill in the form, click
   **Generate JSON snippet**, copy it. Keywords are optional in the form.
2. Paste the object into `grants.json` (inside the top-level array, after a comma).
3. Run `python3 enrich.py` to (re)generate keywords for the new entry, then
   check the file is still valid JSON:
   ```bash
   python3 enrich.py
   python3 -m json.tool grants.json > /dev/null && echo OK
   python3 test_matcher.py   # confirm the 5 example ideas still match sensibly
   ```
4. Commit and push — GitHub Pages redeploys automatically.

Or edit `grants.json` directly, following the schema above. Never guess a URL:
leave `url` as `null` if you cannot copy it verbatim from the official site.

## Run locally

`fetch('grants.json')` is blocked by browsers when the page is opened via
`file://`. Serve the folder instead:

```bash
cd ~/workspace/grants-finder
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy to GitHub Pages

The repo has not been created yet — that is a separate step (parent agent
creates a new public repo, e.g. `grantfinder`, and pushes these files).

1. Create a new **public** repository on GitHub, e.g. `grantfinder`.
2. In this folder:
   ```bash
   git init
   git add index.html grants.json README.md enrich.py test_matcher.py build.py
   git commit -m "GrantFinder v2: idea-matcher over 185 grants & funding programmes for young Indian founders"
   git branch -M main
   git remote add origin https://github.com/<username>/grantfinder.git
   git push -u origin main
   ```
3. On GitHub: **Settings → Pages → Build and deployment → Deploy from a branch**,
   branch `main`, folder `/ (root)`. Save.
4. The site will be live at `https://<username>.github.io/grantfinder/` within a
   minute or two. No build step is needed — it is a static site.

## Regenerating the data

If the two source markdown files are updated, re-run the parser:

```bash
python3 build.py
python3 enrich.py          # re-add keywords (build.py does not generate them)
python3 -m json.tool grants.json > /dev/null && echo "grants.json valid"
python3 test_matcher.py    # confirm the 5 example ideas still match sensibly
```

`build.py` parses every table row and every `###` section in both files,
deduplicates by programme name (keeping the richer entry), flags the 16 Top
Picks and the 10 Quick Wins, and never invents URLs / amounts / deadlines.
Manual additions inside `build.py` are limited to programmes mentioned only in
prose in the source files (Amgen Scholars Asia, Draper Founders Program India,
BRICS Women's Startups Contest, Social Impact Award India, WEP Award to Reward)
— all with URLs copied verbatim from the files or left null.

## Programs that could NOT be fully parsed

These are **not** missing from the site — they are present, but with a gap noted
here (see also the "no URL" count above):

- **24 entries have no URL** (no verbatim URL existed in the research files):
  Amgen Scholars (Asia), ARISE-ANIC, Atal New India Challenge, Cyclotron Road,
  Davis Projects for Peace, Diana Award, Draper Founders Program India,
  Eiffel Excellence Scholarship, Entrepreneur First, GLF Restoration Stewards,
  Habitat Youth Solutions Grant, IAS Youth Hub Seed Grant, Karnataka ELEVATE,
  MeitY GENESIS EIR, MeitY TIDE 2.0, NASA Space Apps Challenge 2026, TechGirls,
  Technovation Girls, Thought For Food Challenge, Urban95 Academy,
  WEP Award to Reward / We Rise, Ye! Youth Ecopreneurs (YECO), Yenching Academy,
  YOUNGO / Conference of Youth / GYCT.
- **49 entries have no parseable USD amount** — mostly "Fully funded",
  "No cash — recognition", in-kind / credit-only, or salary / stipend wordings
  with no single figure. Their verbatim `funding_text` is shown instead.
- **Duplicate-name variants merged**: Atal New India Challenge (listed under both
  Housing and India Government), MeitY TIDE 2.0 (Fintech track + India Government),
  Habitat Youth Solutions Grant, GRP Innovation Challenges, MIT Solve, Grand
  Challenges — each kept once, with the richer entry.
- **Dead / ineligible programmes were deliberately excluded** (they are in the
  source files' "Skip list" / "Verified INELIGIBLE" notes, not as grants):
  e.g. buildspace (discontinued), French Tech Ticket, Unilever Young Entrepreneurs
  Awards, Chivas Venture, Awesome Without Borders, Girls in Tech, 1517 Medici
  cash grants are kept but flagged `india_eligible: false` because the file
  states North-America-only.
- **"See §…" cross-reference rows** in the first file (e.g. "Gates Foundation AI
  Fellowship (India) — See §2") were skipped as rows; the programme itself is
  present under its main section.
