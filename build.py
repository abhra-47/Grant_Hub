#!/usr/bin/env python3
"""Parse Abhrajyoti's two funding-research markdown files into grants.json.
No invented URLs/amounts/deadlines. Unknown -> null / 'Verify on official site'.
"""
import re, json, os
from pathlib import Path

SRC1 = Path.home()/ "workspace/your_files/funding-research/global-fellowships-grants-young-founders.md"
SRC2 = Path.home()/ "workspace/your_files/funding-research/hidden-gems-easy-grants-young-founders.md"
OUT = Path.home()/ "workspace/grants-finder/grants.json"

def clean(s):
    s = re.sub(r'\*\*','', s or '')
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
    s = re.sub(r'<[^>]+>','', s)
    return s.strip(' |').strip()

def slug(name):
    s = re.sub(r'[^a-z0-9]+','-', name.lower()).strip('-')
    return s[:80] or 'grant'

# ---------- URL map: name -> url from "Name https://..." and "- Name: https://..." lines ----------
def build_url_map(text):
    m={}
    for line in text.splitlines():
        # patterns: "Name https://..." separated by · or : or space
        for url in re.findall(r'https?://[^\s\)\]]+', line):
            url=url.rstrip('·,;.')
            # prefix before url
            prefix=line.split(url)[0]
            prefix=clean(re.sub(r'^[-*•\s]+','',prefix))
            # take last segment after · or : or |
            for sep in ['·','|',':']:
                if sep in prefix:
                    prefix=prefix.split(sep)[-1]
            prefix=clean(prefix)
            # strip leading words like "Official URLs", "URLs", "Thiel Fellowship"
            prefix=re.sub(r'^(Official URLs?|URLs?|Sources?)\s*','',prefix,flags=re.I)
            if len(prefix)>=3:
                # store short key: first 2-3 words lower
                m[prefix.lower()]=url
                # also first word+?
    return m

MANUAL_URLS={
 'earthshot prize':'https://earthshotprize.org/people-partners/nominators/',
 'xprize competitions':'https://www.xprize.org',
 'un young champions of the earth':'https://www.unep.org/youngchampions/apply/timeline',
 'youth4climate':'https://www.undp.org/youth4climate',
 'climatelaunchpad':'https://climatelaunchpad.org/',
 'irena newgen accelerator':'https://www.irena.org/Energy-Transition/Partnerships/Youth-Engagement/NewGen-Accelerator',
 'youth climate justice fund':'https://ycjf.org/2026-grant-applications-are-open',
 'google.org ai for social impact':'https://www.google.org/impact-challenges/ai-science/',
 'activate fellowship':'https://www.activate.org/apply',
 '776 fellowship':'https://sevensevensix.com',
 'grand challenges':'https://gcgh.grandchallenges.org',
 'unicef innovation fund':'https://www.unicef.org/innovation/funds',
 'innovation fund (2026: climate & health)':'https://www.unicef.org/innovation/funds',
 'who spark grants':'https://www.inspireopportunities.com/2026/09/who-spark-grants-2026-global-community.html',
 'spark grants 2026':'https://www.inspireopportunities.com/2026/09/who-spark-grants-2026-global-community.html',
 'national geographic society':'https://www.nationalgeographic.com/explorers/grants-programs/yeg-application/',
 'undp youth co:lab (india)':'https://www.undp.org/india/projects/youth-colab-india',
 'bayer foundation fellowships':'https://www.bayer-foundation.com/science/fellowships-stipends',
 'scientific fellowships (medical sciences + climate & health)':'https://www.bayer-foundation.com/science/fellowships-stipends',
 'nidhi-eir':'https://www.indiascienceandtechnology.gov.in/funding-opportunities/startups/nidhi-promoting-and-accelerating-young-and-aspiring-innovators',
 'nidhi-prayas':'https://www.indiascienceandtechnology.gov.in/funding-opportunities/startups/nidhi-promoting-and-accelerating-young-and-aspiring-innovators',
 'schmidt ai in science fellowships':'https://schmidtsciencefellows.org/program/overview/',
}
def lookup_url(urlmap, name, org=''):
    nl=name.lower()
    if nl in MANUAL_URLS: return MANUAL_URLS[nl]
    for k,v in MANUAL_URLS.items():
        if k in nl or nl in k: return v
    best=None
    for k,v in urlmap.items():
        kl=k.lower()
        if kl in nl or nl in kl:
            if best is None or len(k)>len(best[0]): best=(k,v)
    if best: return best[1]
    # token overlap: share a distinctive word (>=6 chars)
    nt=set(re.findall(r'[a-z]{6,}', nl))
    for k,v in urlmap.items():
        kt=set(re.findall(r'[a-z]{6,}', k.lower()))
        if nt & kt: return v
    if org:
        ol=org.lower()
        for k,v in urlmap.items():
            if k.lower() in ol or ol in k.lower(): return v
    return None

# ---------- funding USD ----------
def parse_usd(text):
    if not text: return None, None
    t=text
    # explicit $ in text like (~$260K) etc - collect all $ amounts, take max
    vals=[]
    cur=None
    # USD $X K/M
    for m in re.finditer(r'\$\s*([\d,]+(?:\.\d+)?)\s*([KkMm])?\b', t):
        v=float(m.group(1).replace(',',''))
        mult={'k':1e3,'K':1e3,'m':1e6,'M':1e6}.get(m.group(2),1) if m.group(2) else 1
        vals.append(v*mult); cur='USD'
    # £
    for m in re.finditer(r'£\s*([\d,]+(?:\.\d+)?)\s*([KkMm])?\b', t):
        v=float(m.group(1).replace(',','')); mult={'k':1e3,'K':1e3,'m':1e6,'M':1e6}.get(m.group(2),1) if m.group(2) else 1
        vals.append(v*mult*1.34); cur='GBP'
    for m in re.finditer(r'€\s*([\d,]+(?:\.\d+)?)\s*([KkMm])?\b', t):
        v=float(m.group(1).replace(',','')); mult={'k':1e3,'K':1e3,'m':1e6,'M':1e6}.get(m.group(2),1) if m.group(2) else 1
        vals.append(v*mult*1.17); cur='EUR'
    # SGD
    for m in re.finditer(r'SGD\s*([\d,]+(?:\.\d+)?)\s*([KkMm])?\b', t, re.I):
        v=float(m.group(1).replace(',','')); mult={'k':1e3,'K':1e3,'m':1e6,'M':1e6}.get(m.group(2),1) if m.group(2) else 1
        vals.append(v*mult*0.78); cur='SGD'
    for m in re.finditer(r'CAD\s*\$?\s*([\d,]+(?:\.\d+)?)\s*([KkMm])?\b', t, re.I):
        v=float(m.group(1).replace(',','')); mult={'k':1e3,'K':1e3,'m':1e6,'M':1e6}.get(m.group(2),1) if m.group(2) else 1
        vals.append(v*mult*0.73); cur='CAD'
    # ₹ lakh / crore
    for m in re.finditer(r'₹\s*([\d,]+(?:\.\d+)?)\s*(?:–|-)\s*([\d,]+(?:\.\d+)?)\s*(lakh|crore|L)', t):
        v=float(m.group(2).replace(',','')); vals.append(v*(100000 if m.group(3).lower().startswith('lakh') or m.group(3)=='L' else 10000000)/88); cur='INR'
    for m in re.finditer(r'₹\s*([\d,]+(?:\.\d+)?)\s*(lakh|crore|L)\b', t):
        v=float(m.group(1).replace(',','')); vals.append(v*(100000 if m.group(2).lower().startswith('lakh') or m.group(2)=='L' else 10000000)/88); cur='INR'
    # ₹ plain numbers like ₹10,00,000 / ₹25,00,000 / ₹1 crore handled above; also ₹70K
    for m in re.finditer(r'₹\s*([\d,]+(?:\.\d+)?)\s*([Kk])\b', t):
        vals.append(float(m.group(1).replace(',',''))*1000/88); cur='INR'
    for m in re.finditer(r'₹\s*([\d,]+(?:\.\d+)?)\b', t):
        # only if no lakh/crore already and number large (>10000)
        v=float(m.group(1).replace(',',''))
        if v>=10000 and 'lakh' not in t.lower() and 'crore' not in t.lower():
            vals.append(v/88); cur='INR'
    # ₩
    for m in re.finditer(r'₩\s*([\d,]+)M', t):
        vals.append(float(m.group(1).replace(',',''))*1e6/1350); cur='KRW'
    if not vals:
        return None, None
    return int(round(max(vals))), (cur or 'USD')

def deadline_status(deadline):
    d=(deadline or '').lower()
    if 'rolling' in d: return 'rolling'
    if 'closed' in d and 'open' not in d: return 'closed'
    if 'open now' in d or 'live' in d or 'apply now' in d: return 'open-now'
    if 'unverified' in d or 'verify' in d or not d.strip(): return 'unverified'
    if re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s*2026|2026|2027', d): return 'dated'
    return 'unverified'

def india_eligible(elig, name=''):
    t=(elig or '').lower()
    if any(p in t for p in ['india not eligible','india not on','india-blocked','india eligibility unverified','ineligible for india','us-only','us citizens','africa-only','africa only','north america only','us schools only','itar-blocked','india not a participating']):
        # careful: "India eligibility unverified" -> unknown, not false
        if 'unverified' in t or 'not verifiable' in t:
            return 'unknown'
        return False
    if any(p in t for p in ['india','indian','iit bombay','dpiit','south asia']):
        return True
    return 'unknown'

def infer_type(name, funding=''):
    n=(name+' '+funding).lower()
    if 'scholarship' in n: return 'Scholarship'
    if 'fellowship' in n: return 'Fellowship'
    if 'accelerator' in n: return 'Accelerator'
    if 'hackathon' in n: return 'Competition'
    if 'challenge' in n: return 'Competition'
    if 'prize' in n or 'award' in n: return 'Prize'
    if 'competition' in n: return 'Competition'
    if 'credits' in n or 'cloud' in n: return 'Credits'
    if 'grant' in n: return 'Grant'
    return 'Grant'

def infer_category_from_domains(domains):
    d=(domains or '').lower()
    if any(k in d for k in ['climate','clean energy','ocean','biodiversity','environment','carbon','sustainab','restoration','conservation','species','wildlife']): return 'Climate & Environment'
    if any(k in d for k in ['health','biotech','medical','pharma','ageing','bioscience','mental health']): return 'Healthcare & Biotech'
    if any(k in d for k in ['quantum','ai','tech','software','open source','foss','internet','web3','crypto','blockchain','ethereum','solana','data science','ml','hackathon','dev']): return 'Tech & AI'
    if 'space' in d: return 'Space'
    if any(k in d for k in ['mobility','transport','urban','housing','water']): return 'Water, Housing & Urban' if 'water' in d else 'Housing & Urban'
    if any(k in d for k in ['agri','food','farm']): return 'Agriculture & Food'
    if any(k in d for k in ['fintech','finance','financial']): return 'Finance & Fintech'
    if any(k in d for k in ['gender','women']): return 'Gender Equality'
    if 'education' in d: return 'Education'
    if any(k in d for k in ['art','film','storytelling','literature','essay','design']): return 'Arts, Culture & Media'
    if any(k in d for k in ['social','livelihood','poverty','disability','assistive']): return 'Social Impact'
    return 'General / Multi-domain'

CAT_MAP = {
 '1. Climate':'Climate & Environment','2. Healthcare':'Healthcare & Biotech','3. Tech':'Tech & AI',
 '4. Space':'Space','5. Mobility':'Mobility & Transport','6. Agriculture':'Agriculture & Food',
 '7. Finance':'Finance & Fintech','8. Housing':'Housing & Urban','9. Disaster':'Disaster Resilience',
 '10. Social':'Social Impact','11. Gender':'Gender Equality','12. Education':'Education',
 '13. Arts':'Arts, Culture & Media','14. Academic':'Academic Fellowships','15. India':'India Government',
}

entries=[]  # dicts
def add(e):
    # normalize name for dedup
    key=re.sub(r'[^a-z0-9]','', e['name'].lower())
    # strip common suffixes
    e['_key']=key
    entries.append(e)

def parse_file1(text, urlmap):
    lines=text.splitlines()
    # Top picks
    top_names=[]
    in_top=False
    for line in lines:
        if line.startswith('## ⭐ Top Picks'): in_top=True; continue
        if in_top and line.startswith('###'): in_top=False
        if in_top and line.startswith('|') and '**' in line:
            m=re.search(r'\*\*([^*]+)\*\*', line)
            if m: top_names.append(clean(m.group(1)))
    # sections
    current_cat='General / Multi-domain'
    i=0
    while i < len(lines):
        line=lines[i]
        m=re.match(r'##\s+(\d+)\.\s+(.+)', line)
        if m:
            num=m.group(1); title=m.group(2)
            for k,v in CAT_MAP.items():
                if k.startswith(num+'.'): current_cat=v
            i+=1; continue
        # table row
        if line.startswith('|') and 'Program' not in line and '---' not in line:
            cells=[clean(c) for c in line.strip().strip('|').split('|')]
            if len(cells)>=4:
                # Top picks table has 3 cells, handled separately below
                if len(cells)==3 and current_cat=='General / Multi-domain':
                    i+=1; continue
                name, org, elig, fund = cells[0], cells[1], cells[2], cells[3] if len(cells)>3 else ''
                deadline = cells[4] if len(cells)>4 else ''
                name=clean(name)
                if name.startswith('Atal New India Challenge'): name='Atal New India Challenge'
                if name.startswith('MeitY TIDE 2.0'): name='MeitY TIDE 2.0'
                if name.startswith('Habitat Youth Solutions Grant'): name='Habitat Youth Solutions Grant'
                if name.startswith('GRP Innovation Challenges'): name='GRP Innovation Challenges'
                if name.startswith('MIT Solve'): name='MIT Solve'
                if name.startswith('Grand Challenges'): name='Grand Challenges'
                if not name or name.lower().startswith('program'): i+=1; continue
                if 'see §' in (elig+fund).lower() or 'see §' in name.lower():
                    i+=1; continue
                # strip leading ** etc already
                url=lookup_url(urlmap, name, org)
                usd, cur = parse_usd(fund)
                e=dict(name=name, org=org, category=current_cat, type=infer_type(name), funding_text=fund or 'Verify on official site',
                       funding_amount_usd=usd, funding_currency=cur, eligibility=elig, deadline_text=deadline or 'Verify on official site',
                       deadline_status=deadline_status(deadline), india_eligible=india_eligible(elig), url=url,
                       why_easy=None, is_hidden_gem=False, is_top_pick=any(clean(t).lower() in name.lower() or name.lower() in clean(t).lower() for t in top_names),
                       is_quick_win=False, source_file='global-fellowships-grants-young-founders.md')
                add(e)
        i+=1
    # Top picks entries not already in tables (Halcyon etc already in tables, but ensure)
    # Parse top picks table explicitly for funding/deadline
    for line in lines:
        if line.startswith('|') and '**' in line and '—' in line:
            # only in top section? approximate: check if line contains $ or ₹ and "Why it stands out" context - skip, tables already cover
            pass
    return top_names

def parse_file2(text, urlmap):
    lines=text.splitlines()
    quick_names=[]
    in_q=False
    for line in lines:
        if 'Quick wins' in line: in_q=True; continue
        if in_q and line.startswith('##'): in_q=False
        if in_q and line.startswith('|') and '**' in line:
            m=re.search(r'\*\*([^*]+)\*\*', line)
            if m: quick_names.append(clean(m.group(1)))
    # ### sections
    i=0
    while i < len(lines):
        line=lines[i]
        m=re.match(r'###\s+(.+?)(?:\s+⭐.*)?$', line)
        if m:
            title=clean(m.group(1))
            # remove trailing star markers
            title=re.sub(r'\s*⭐.*$','',title).strip()
            # title may be "Awesome Foundation — Monthly $1,000 Micro-grants"
            name=title.split(' — ')[0].split(' - ')[0].strip()
            if 'Roddenberry' in title: name='Roddenberry Catalyst Fund'
            if 'MSME Idea Hackathon' in title: name='MSME Idea Hackathon'
            if title.startswith('Stellar Community Fund'): name='Stellar Community Fund'
            if title.startswith('FOSS United'): name='FOSS United Grants'
            if title.startswith('D-Prize'): name='D-Prize'
            if title.startswith('Kaggle'): name='Kaggle — ARC Prize 2026'
            if title.startswith('DrivenData'): name='DrivenData — GEMS Prize Challenge'
            # collect bullet block until next ## / ###
            block=[]
            j=i+1
            while j < len(lines) and not lines[j].startswith('##') and not lines[j].startswith('###'):
                block.append(lines[j]); j+=1
            btext='\n'.join(block)
            def field(label):
                mm=re.search(r'\*\*'+re.escape(label)+r':\*\*\s*(.+?)(?:\s\*\*[A-Z][^*]+:\*\*|\n- \*\*|\n\n|\Z)', btext, re.S)
                if mm: return clean(mm.group(1).replace('\n',' '))
                for bl in block:
                    if label.lower() in bl.lower():
                        return clean(re.sub(r'^.*?\*\*'+re.escape(label)+r':\*\*\s*','',bl))
                return ''
            org=field('Org'); elig=field('Eligibility'); fund=field('Funding'); dead=field('Deadline'); why=field('Why low-competition')
            # Org field contains domains after · - split
            domains=''
            if '·' in org:
                parts=org.split('·'); org=parts[0].strip()
                if len(parts)>1: domains=parts[1]
            # also Domains in org line: "Domains:" 
            dm=re.search(r'Domains:\s*(.+?)(?:\n|$)', btext)
            if dm: domains=dm.group(1)
            url=None
            um=re.search(r'https?://[^\s\)\]]+', btext)
            if um: url=um.group(0).rstrip('·,;.')
            elif 'unverified' in btext.lower():
                url=None
            else:
                url=lookup_url(urlmap, name, org)
            # funding/deadline may be embedded in same bullet as Funding:
            usd, cur = parse_usd(fund)
            cat=infer_category_from_domains(domains) if domains and domains.strip().lower() not in ('any','any (each chapter interprets "awesome" itself)') else 'General / Multi-domain'
            # if domains empty, use section size? keep General
            e=dict(name=name, org=org, category=cat, type=infer_type(name, fund), funding_text=fund or 'Verify on official site',
                   funding_amount_usd=usd, funding_currency=cur, eligibility=elig or 'Verify on official site',
                   deadline_text=dead, deadline_status=deadline_status(dead), india_eligible=india_eligible(elig), url=url,
                   why_easy=why or None, is_hidden_gem=True,
                   is_top_pick=False, is_quick_win=any(clean(q).lower() in name.lower() or name.lower() in clean(q).lower() for q in quick_names),
                   source_file='hidden-gems-easy-grants-young-founders.md')
            add(e)
            i=j; continue
        i+=1
    return quick_names

text1=SRC1.read_text(); text2=SRC2.read_text()
urlmap={**build_url_map(text1), **build_url_map(text2)}
# also manual URL fixes from Sources / explicit lines in text1
# Extract "- Name: https://..." from Sources
for line in text1.splitlines()+text2.splitlines():
    m=re.match(r'-\s+([^:]+):\s+(https?://\S+)', line.strip())
    if m:
        urlmap[clean(m.group(1)).lower()]=m.group(2).rstrip('.')

top=parse_file1(text1, urlmap)
quick=parse_file2(text2, urlmap)
print("raw entries", len(entries), "top", top, "quick", quick)

# Manual additions for programs mentioned only in prose / Also lines (verified in files, no invented URLs)
manual=[
 dict(name="Amgen Scholars Asia", org="Amgen Foundation", category="Academic Fellowships", type="Fellowship", funding_text="Fully funded 8–9 wk research summer (stipend, travel, accommodation)", funding_amount_usd=None, funding_currency=None, eligibility="Undergrads at Asian universities incl. India (completed ≥1st yr)", deadline_text="Opens ~Nov 2026 (unverified)", deadline_status="unverified", india_eligible=True, url=None, why_easy=None, is_hidden_gem=False, is_top_pick=False, is_quick_win=False, source_file="global-fellowships-grants-young-founders.md"),
 dict(name="Draper Founders Program India", org="Draper University", category="Tech & AI", type="Accelerator", funding_text="$15,000 scholarships (2025, 2 founders in Hyderabad)", funding_amount_usd=15000, funding_currency="USD", eligibility="Indian founders; Draper Founders Program India (Hyderabad)", deadline_text="Verify on official site", deadline_status="unverified", india_eligible=True, url=None, why_easy="Side door — scholarships, not the paid Hero Training", is_hidden_gem=True, is_top_pick=False, is_quick_win=False, source_file="hidden-gems-easy-grants-young-founders.md"),
 dict(name="BRICS Women's Startups Contest 2026", org="BRICS", category="Social Impact", type="Competition", funding_text="Cash terms unverified", funding_amount_usd=None, funding_currency=None, eligibility="Women-led startups from BRICS nations; 2026 edition India-led", deadline_text="Verify on official site", deadline_status="unverified", india_eligible=True, url="https://www.archynewsy.com/brics-womens-startups-contest-2026-apply-now/", why_easy="2026 edition India-led = home-turf advantage", is_hidden_gem=True, is_top_pick=False, is_quick_win=False, source_file="hidden-gems-easy-grants-young-founders.md"),
 dict(name="Social Impact Award India", org="Social Impact Award", category="Social Impact", type="Fellowship", funding_text="Incubation, not a cash grant", funding_amount_usd=None, funding_currency=None, eligibility="Youth social entrepreneurs in India; 2025 aim: 100+ incubated across 20+ Tier-II/III cities", deadline_text="Verify on official site", deadline_status="unverified", india_eligible=True, url="https://india.socialimpactaward.net/about-discovery-host/", why_easy="New in India, very low visibility", is_hidden_gem=True, is_top_pick=False, is_quick_win=False, source_file="hidden-gems-easy-grants-young-founders.md"),
 dict(name="WEP Award to Reward / We Rise", org="NITI Aayog (WEP)", category="Gender Equality", type="Prize", funding_text="Recognition + market access, not cash", funding_amount_usd=None, funding_currency=None, eligibility="Women entrepreneurs in India", deadline_text="Verify on official site", deadline_status="unverified", india_eligible=True, url=None, why_easy="Govt-platform obscurity = thin pools (600 applications nationally)", is_hidden_gem=True, is_top_pick=False, is_quick_win=False, source_file="hidden-gems-easy-grants-young-founders.md"),
]
for e in manual:
    e['_key']=re.sub(r'[^a-z0-9]','', e['name'].lower())
    entries.append(e)

# Deduplicate: keep richer entry
by={}
for e in entries:
    k=e['_key']
    if k not in by:
        by[k]=e
    else:
        old=by[k]
        # score richness
        def score(x): return len(x.get('eligibility') or '')+len(x.get('funding_text') or '')+(50 if x.get('url') else 0)+(20 if x.get('why_easy') else 0)
        if score(e)>score(old):
            # merge flags
            e['is_hidden_gem']=e['is_hidden_gem'] or old['is_hidden_gem']
            e['is_top_pick']=e['is_top_pick'] or old['is_top_pick']
            e['is_quick_win']=e['is_quick_win'] or old['is_quick_win']
            if not e.get('why_easy'): e['why_easy']=old.get('why_easy')
            if not e.get('url'): e['url']=old.get('url')
            by[k]=e
        else:
            old['is_hidden_gem']=old['is_hidden_gem'] or e['is_hidden_gem']
            old['is_top_pick']=old['is_top_pick'] or e['is_top_pick']
            old['is_quick_win']=old['is_quick_win'] or e['is_quick_win']
            if not old.get('why_easy'): old['why_easy']=e.get('why_easy')
            if not old.get('url'): old['url']=e.get('url')

dedup=list(by.values())
# Fix top picks / quick wins by name matching (in case table parse missed)
TOP16=["Thiel Fellowship","MATS Winter 2027 Residency","Y Combinator","Hult Prize","Echoing Green Fellowship","776 Fellowship","Gates Grand Challenges","Emergent Ventures","Google.org Impact Challenge","MIT Solve","UNICEF Innovation Fund","BIRAC Biotechnology Ignition Grant","UN Young Champions of the Earth","Youth4Climate","Startup India Seed Fund","Halcyon Flagship Residential Fellowship"]
for e in dedup:
    for t in TOP16:
        if t.lower() in e['name'].lower() or e['name'].lower() in t.lower():
            e['is_top_pick']=True
    nl=e['name'].lower()
    if ('birac' in nl and 'big' in nl) or 'google.org ai' in nl or ('innovation fund' in nl and 'unicef' in e.get('org','').lower()) or nl.startswith('unicef innovation'):
        e['is_top_pick']=True
    # Gates Grand Challenges India is a different programme from the global Gates one - unflag it
    if e['name']=='Gates Grand Challenges India':
        e['is_top_pick']=False
    if 'roddenberry catalyst' in nl or 'msme idea hackathon' in nl:
        e['is_quick_win']=True
    if e['name']=='Google.org AI grants (AI Opportunity Fund)':
        e['is_top_pick']=False
    if e['name']=='D-Prize':
        e['category']='Social Impact'
    # clean id etc
for e in dedup:
    e['id']=slug(e['name'])
    # ensure india_eligible is bool/unknown string as spec: keep true/false/'unknown'
    del e['_key']
    # trim long fields
    for f in ['name','org','category','type','funding_text','eligibility','deadline_text']:
        if e.get(f): e[f]=clean(str(e[f]))[:600]

dedup.sort(key=lambda x: x['name'].lower())
# fix duplicate ids
seen={}
for e in dedup:
    if e['id'] in seen:
        e['id']=e['id']+'-'+str(seen[e['id']])
        seen[e['id']]=1
    else:
        seen[e['id']]=1

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(dedup, indent=2, ensure_ascii=False))
print("dedup", len(dedup))
from collections import Counter
print(Counter(x['category'] for x in dedup))
print(Counter(str(x['india_eligible']) for x in dedup))
print("top", sum(1 for x in dedup if x['is_top_pick']), "gem", sum(1 for x in dedup if x['is_hidden_gem']), "quick", sum(1 for x in dedup if x['is_quick_win']))
print("no url", sum(1 for x in dedup if not x['url']))
for x in dedup:
    if not x['url']:
        print(" NOURL:", x['name'])
