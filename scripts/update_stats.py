"""Build public GitHub stats as an SVG; no external image service."""
import os, json, math
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from html import escape

ROOT = Path(__file__).resolve().parents[1]
USER = "antoniomarcoos"
def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "middle-earth-profile"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request("https://api.github.com/" + path, headers=headers), timeout=30) as response:
        return json.load(response)
def search(kind):
    return api("search/" + kind)["total_count"]
repos = []
for page in range(1, 11):
    batch = api(f"users/{USER}/repos?per_page=100&page={page}&sort=pushed")
    repos.extend(batch)
    if len(batch) < 100: break
owned = [r for r in repos if not r["fork"]]
def recent(repo):
    try:
        return repo, api(f"repos/{repo['full_name']}/commits?author={USER}&per_page=100")
    except Exception as exc:
        if getattr(exc, "code", None) == 409: return repo, []
        raise
with ThreadPoolExecutor(max_workers=4) as pool:
    sampled = list(pool.map(recent, owned[:20]))
hours = Counter()
langs_commit = Counter()
seen = set()
for repo, commits in sampled:
    for commit in commits:
        if commit["sha"] in seen: continue
        seen.add(commit["sha"])
        date = datetime.fromisoformat(commit["commit"]["author"]["date"].replace("Z", "+00:00"))
        hours[date.astimezone(timezone(timedelta(hours=-3))).hour] += 1
        if repo["language"]: langs_commit[repo["language"]] += 1
langs_repo = Counter(r["language"] for r in owned if r["language"])
metrics = [("Stars", sum(r["stargazers_count"] for r in owned)),
           ("Public commits", search(f"commits?q=author:{USER}")),
           ("Pull requests", search(f"issues?q=author:{USER}+type:pr")),
           ("Issues", search(f"issues?q=author:{USER}+type:issue")),
           ("Original repositories", len(owned))]
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="530" viewBox="0 0 1000 530" role="img" aria-labelledby="title desc"><title id="title">Chronicles of the journey — GitHub statistics</title><desc id="desc">Public GitHub statistics. Hourly activity and commit language distributions use a recent sample from up to twenty original repositories. Commit languages refer to the primary language of each repository.</desc><rect width="1000" height="530" rx="16" fill="#0d1117"/>']
def text(x,y,value,size=13,color="#a7b19d",anchor="start",serif=False):
    font = "Georgia,serif" if serif else "monospace"
    parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="{font}" font-size="{size}" text-anchor="{anchor}">{escape(str(value))}</text>')
def heading(x,y,value):
    text(x,y,value,21,"#d3bd82",serif=True)
    parts.append(f'<path d="M{x} {y+12}h390" stroke="#776b48" stroke-opacity=".45"/>')
text(500,35,"CHRONICLES OF THE JOURNEY",18,"#d3bd82","middle",True)
heading(50,82,"The record so far")
for i,(label,value) in enumerate(metrics):
    text(58,116+i*25,label); text(430,116+i*25,f"{value:,}",14,"#d3bd82","end")
heading(530,82,"Commits by hour · UTC−3")
maximum = max(hours.values(), default=1)
for h in range(24):
    height = hours[h]/maximum*119
    parts.append(f'<rect x="{540+h*15.5}" y="{228-height}" width="11" height="{height}" rx="2" fill="#b8a56d"><title>{h:02d}:00 — {hours[h]} commits in sample</title></rect>')
for h in (0,6,12,18,23): text(545+h*15.5,247,h,10,anchor="middle")
colors = ["#c9b376", "#7d967b", "#a4785b", "#577c7a", "#8f829d", "#766d4a"]
def donut(x,y,title,counter):
    heading(x,y,title)
    items = counter.most_common(5)
    other = sum(counter.values())-sum(v for _,v in items)
    if other: items.append(("Other",other))
    total = sum(counter.values())
    cx,cy=x+290,y+100
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="60" fill="none" stroke="#24332f" stroke-width="20"/>')
    offset=0
    for i,(label,count) in enumerate(items):
        fraction=count/total
        circumference=2*math.pi*60
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="60" fill="none" stroke="{colors[i]}" stroke-width="20" stroke-dasharray="{fraction*circumference} {circumference}" stroke-dashoffset="{-offset*circumference}" transform="rotate(-90 {cx} {cy})"><title>{escape(label)}: {count}</title></circle>')
        offset+=fraction
        parts.append(f'<rect x="{x+7}" y="{y+37+i*24}" width="9" height="9" rx="2" fill="{colors[i]}"/>')
        text(x+24,y+46+i*24,f"{label} {fraction:.0%}",12)
    text(cx,cy+5,total,22,"#d3bd82","middle",True)
donut(50,300,"Languages by repository",langs_repo)
donut(530,300,"Languages by recent commits",langs_commit)
text(500,495,f"PUBLIC DATA · RECENT SAMPLE: {len(seen):,} COMMITS · COMMIT LANGUAGE = REPOSITORY PRIMARY LANGUAGE",9,"#87917e","middle")
text(500,516,"Updated "+datetime.now(timezone.utc).strftime("%Y-%m-%d")+" · Original public repositories · Indexed public commit total",9,"#87917e","middle")
parts.append('</svg>')
output=ROOT/"assets/profile-stats.svg"
output.parent.mkdir(exist_ok=True)
output.with_suffix(".tmp").write_text("".join(parts))
output.with_suffix(".tmp").replace(output)
print(f"Generated stats: {len(owned)} repos, {len(seen)} sampled commits")
