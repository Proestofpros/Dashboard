"""Daily job scrape -> jobs.json. Needs env var APIFY_TOKEN. Uses Apify's run-sync API."""
import os, re, json, sys, time, datetime as dt, requests

TOKEN = os.environ["APIFY_TOKEN"]
BASE = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items"
PFX = {"L": "https://in.linkedin.com/jobs/view/", "N": "https://www.naukri.com/job-listings-", "F": "https://www.foundit.in/job/"}
OUT = os.path.join(os.path.dirname(__file__), "..", "jobs.json")
NOW = dt.datetime.now(dt.timezone.utc)

def run(actor, inp):
    for _ in range(2):
        try:
            r = requests.post(BASE.format(actor.replace("/", "~")), params={"token": TOKEN, "clean": "true"}, json=inp, timeout=290)
            if r.ok:
                return r.json()
            print(actor, r.status_code, r.text[:200], file=sys.stderr)
        except Exception as e:
            print(actor, e, file=sys.stderr)
        time.sleep(5)
    return None

def g(d, path):
    """Read 'a.b' from nested or flattened items."""
    if path in d: return d[path]
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur: return None
        cur = cur[k]
    return cur

SEN = re.compile(r"senior|\bsr\b|\blead\b|manager|\bhead\b|principal|director|architect|\bstaff\b|\bvp\b|intern(ship)?\b|trainer|sales|telecall|recruit|bpo|teacher", re.I)
def role(t):
    if re.search(r"civil|site engineer|structural|highway|road|quantity survey|construction|site coordinator", t, re.I): return 76
    if re.search(r"\b(qa|quality assurance|software tester|test engineer|manual test|testing|tester)\b", t, re.I): return 80
    if re.search(r"data analyst|analytics|\bmis\b|reporting|power ?bi|data analysis", t, re.I): return 80
    if re.search(r"business analyst|business analysis", t, re.I): return 78
    if re.search(r"research analyst|financial analyst|junior analyst|associate analyst", t, re.I): return 76
    return 0

def score(t, mn, mx, lvl, easy, sal):
    s = role(t)
    if not s or SEN.search(t): return 0
    if mn is not None and mn >= 3: return 0
    if mn is not None and mn >= 2: s -= 4
    if re.search(r"mid|senior|director|executive", lvl or "", re.I): return 0
    if re.search(r"fresher|entry|trainee|junior|graduate|associate", t, re.I) or (mx is not None and mx <= 1) or re.search(r"entry", lvl or "", re.I): s += 4
    if easy: s += 2
    if sal: s += 1
    return min(s, 90)

def ago(txt):
    m = re.search(r"(\d+)\s*(minute|hour|day|week)", str(txt or ""), re.I)
    if not m: return NOW
    unit = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800}[m.group(2).lower()]
    return NOW - dt.timedelta(seconds=int(m.group(1)) * unit)

def label(d): return d.strftime("%b ") + str(d.day)
def short_loc(s): return (s or "See listing").split(",")[0].strip() or "See listing"

def row(src, title, co, loc, sc, apply, sal, url, when):
    if sc < 75 or not str(url).startswith("http") or not url.startswith(PFX[src]): return None
    return [title, co or "Not shown", loc or "See listing", sc, apply, sal or "", src, url[len(PFX[src]):], label(when)]

def lakh(label_):
    m = re.match(r"\s*([\d.]+)\s*-\s*([\d.]+)\s*Lacs", str(label_ or ""))
    return f"₹{m.group(1)}–{m.group(2)} LPA" if m else ""

def map_l(x):
    easy = "EASY" in str(x.get("applyType", "")).upper()
    sal = x.get("salary") or ""
    return row("L", x["title"], x.get("companyName"), short_loc(x.get("location")), score(x["title"], None, None, x.get("experienceLevel"), easy, sal), "Easy Apply" if easy else "External", sal, x.get("url", ""), ago(x.get("postedTimeAgo")))

def map_n(x):
    ex = str(g(x, "experience.text") or ""); m = re.search(r"(\d+)\s*-\s*(\d+)", ex)
    mn, mx = (int(m.group(1)), int(m.group(2))) if m else (0, None)
    sal = lakh(g(x, "salary.label")); loc = None
    ls = g(x, "locations")
    if isinstance(ls, list) and ls and isinstance(ls[0], dict): loc = ls[0].get("label")
    loc = loc or g(x, "locations.label")
    when = NOW
    try: when = dt.datetime.strptime(str(x.get("createdDateText"))[:10], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    except Exception: pass
    return row("N", x["title"], g(x, "company.name"), short_loc(loc), score(x["title"], mn, mx, "", False, sal), "Company site" if x.get("companyApplyJob") else "Naukri Apply", sal, x.get("url", ""), when)

def map_f(x):
    lo, hi = x.get("salary_min_lakhs"), x.get("salary_max_lakhs")
    sal = f"₹{lo}–{hi} LPA" if lo and hi else ""
    return row("F", x["title"], x.get("company"), short_loc(x.get("location")), score(x["title"], x.get("experience_min_years") or 0, x.get("experience_max_years"), "", False, sal), "Foundit", sal, x.get("apply_url", ""), NOW - dt.timedelta(days=x.get("posted_days_ago") or 0))

SEARCHES = []
for k in ["Data Analyst", "Business Analyst fresher", "QA Analyst manual testing", "Civil Engineer"]:
    SEARCHES.append(("L", map_l, "valig/linkedin-jobs-scraper", {"datePosted": "r86400", "keywords": k, "limit": 30, "location": "India", "titleExclude": ["Senior", "Lead", "Manager", "Head", "Principal", "Sr", "Director"]}))
for k in ["Data Analyst", "Business Analyst", "QA Tester Manual Testing", "Civil Engineer"]:
    SEARCHES.append(("N", map_n, "valig/naukri-jobs-scraper", {"experience": 0, "jobAge": "1", "keywords": k, "limit": 30, "location": "India", "sort": "f"}))
for k in ["Data Analyst", "Business Analyst", "QA Tester", "Civil Engineer"]:
    SEARCHES.append(("F", map_f, "themineworks/foundit-jobs-scraper", {"experienceMaxYears": 2, "location": "India", "maxJobs": 20, "postedWithinDays": "1", "searchKeywords": [k]}))

fresh = {"L": [], "N": [], "F": []}; ok = {"L": 0, "N": 0, "F": 0}
for src, mapper, actor, inp in SEARCHES:
    items = run(actor, inp)
    if items is None: continue
    ok[src] += 1
    for x in items:
        if isinstance(x, dict) and x.get("title"):
            try:
                r = mapper(x)
                if r: fresh[src].append(r)
            except Exception as e:
                print("skip", e, file=sys.stderr)

old = []
try: old = json.load(open(OUT, encoding="utf-8")).get("rows", [])
except Exception: pass

rows, seen = [], set()
for src in "LNF":
    pool = fresh[src] if ok[src] else [r for r in old if r[6] == src]  # keep old rows if a source fully failed
    for r in pool:
        k = re.sub(r"[^a-z0-9]", "", (r[0] + r[1]).lower())
        if k in seen: continue
        seen.add(k); rows.append(r)
rows.sort(key=lambda r: (-r[3], 0 if r[4] == "Easy Apply" else 1))
if not rows:
    sys.exit("No rows produced; leaving jobs.json unchanged.")
json.dump({"updated": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"wrote {len(rows)} rows; searches ok: {ok}")
