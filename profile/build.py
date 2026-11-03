#!/usr/bin/env python3
"""Builds this profile: reads my activity on GitHub, draws the SVGs in img/ and writes README.md.

    python profile/build.py             fetch from GitHub, then build
    python profile/build.py --offline   build from profile/cache only

Edit profile/README.tpl.md (text) and profile/profile.toml (settings), never README.md.
Standard library only, Python 3.11+.
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import re
import string
import tomllib
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "profile"
CACHE = HERE / "cache"
IMG = ROOT / "img"
CFG = tomllib.loads((HERE / "profile.toml").read_text(encoding="utf-8"))

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
# Odoo's plum for merged work, Odoo's teal for work still in review, on GitHub's own greys.
THEMES = {
    "light": {"ink": "#1f2328", "muted": "#656d76", "line": "#d0d7de", "grid": "#eaeef2",
              "merged": "#714b67", "open": "#017e84"},
    "dark": {"ink": "#e6edf3", "muted": "#8d96a0", "line": "#30363d", "grid": "#21262d",
             "merged": "#c58fb9", "open": "#39c5cc"},
}


# ================================================================ GitHub

def request(url, body=None, token=None):
    headers = {"User-Agent": "profile-readme-builder", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=30) as res:
        return res.read().decode()


def calendar_from_profile(user):
    """The contribution graph of the public profile: the same numbers visitors see."""
    page = request(f"https://github.com/users/{user}/contributions")
    dates = {cid: day for day, cid in re.findall(r'data-date="([\d-]+)"[^>]*?id="([^"]+)"', page)}
    counts = {}
    for cid, tip in re.findall(r'<tool-tip[^>]*?for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        if cid in dates:
            n = re.match(r"(\d+) contribution", tip)
            counts[dates[cid]] = int(n.group(1)) if n else 0
    return counts


def calendar_from_graphql(user, token):
    query = ("query($u:String!){user(login:$u){contributionsCollection{contributionCalendar"
             "{weeks{contributionDays{date contributionCount}}}}}}")
    body = json.dumps({"query": query, "variables": {"u": user}}).encode()
    res = json.loads(request("https://api.github.com/graphql", body, token))
    if res.get("errors"):
        raise SystemExit(f"GraphQL: {res['errors']}")
    weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def fetch_calendar(user, token):
    try:
        counts = calendar_from_profile(user)
        if len(counts) > 300:
            return counts
        print(f"profile page: only {len(counts)} days found")
    except OSError as exc:
        print(f"profile page: {exc}")
    if not token:
        raise SystemExit("No contribution calendar: the profile page failed and GITHUB_TOKEN is not set.")
    return calendar_from_graphql(user, token)


def fetch_pulls(user, token):
    q = urllib.parse.quote(f"type:pr author:{user} is:public")
    items = []
    for page in range(1, 11):  # the search API stops at 1,000 results
        res = json.loads(request(f"https://api.github.com/search/issues?q={q}&sort=created&order=desc"
                                 f"&per_page=100&page={page}", token=token))
        items += res["items"]
        if len(res["items"]) < 100:
            break
    return [{"title": i["title"], "url": i["html_url"], "repo": i["repository_url"].split("/repos/", 1)[1],
             "state": i["state"], "opened": i["created_at"][:10],
             "merged": (i["pull_request"].get("merged_at") or "")[:10] or None} for i in items]


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    calendar = dict(sorted(fetch_calendar(CFG["user"], token).items()))
    pulls = fetch_pulls(CFG["user"], token)
    CACHE.mkdir(exist_ok=True)
    (CACHE / "calendar.json").write_text(json.dumps(calendar, indent=0) + "\n", encoding="utf-8")
    (CACHE / "pulls.json").write_text(json.dumps(pulls, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ================================================================ data helpers

def status(p):
    return "merged" if p["merged"] else "open" if p["state"] == "open" else "closed"


def odoo_version(p):
    m = re.search(r"\[(\d+\.0)\]", p["title"]) or re.search(r"\b(\d+\.0)\b", p["title"])
    return m.group(1) if m else "other"


def split_title(title):
    """'[18.0][ADD] module: what' -> (['18.0'], ['ADD'], 'module: what')"""
    tags, rest = re.match(r"((?:\[[^\]]*\]\s*)*)(.*)", title).groups()
    tags = re.findall(r"\[([^\]]*)\]", tags)
    is_version = lambda t: re.fullmatch(r"\d+\.0", t)
    return [t for t in tags if is_version(t)], [t for t in tags if not is_version(t)], rest


def weekly(days):
    """52 weekly totals, the last week ending today: [(first day, total)]."""
    days = days[-364:]
    return [(days[k][0], sum(c for _, c in days[k:k + 7])) for k in range(0, len(days), 7)]


def short(d):
    return f"{d:%b} {d.day}"


# ================================================================ SVG helpers

def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{MONO}"><defs>{defs}</defs>{body}</svg>\n')


def smooth(points, floor):
    """A Catmull-Rom curve through the points, as cubic Béziers that never dip below `floor`."""
    d = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    for k in range(len(points) - 1):
        p0, p1 = points[max(k - 1, 0)], points[k]
        p2, p3 = points[k + 1], points[min(k + 2, len(points) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, min(floor, p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, min(floor, p2[1] - (p3[1] - p1[1]) / 6))
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


# ================================================================ header: name + a year of activity as one signal

def header_svg(t, days, pulls):
    W, H = 1200, 318
    x0, x1, base, amp = 24, 1176, 262, 118
    weeks = weekly(days)
    peak = max(v for _, v in weeks) or 1
    pts = [(x0 + k * (x1 - x0) / (len(weeks) - 1), base - amp * math.sqrt(v / peak)) for k, (_, v) in enumerate(weeks)]
    line = smooth(pts, base)
    total = sum(c for _, c in days[-364:])

    out = [f'<text x="22" y="74" font-family="{SANS}" font-size="50" font-weight="700" fill="{t["ink"]}">{esc(CFG["name"])}</text>',
           f'<text x="24" y="110" font-family="{SANS}" font-size="20" fill="{t["muted"]}">{esc(CFG["role"])}</text>']

    # numbers as pills, right-aligned
    work = [p for p in pulls if status(p) != "closed"]
    repos = {p["repo"] for p in work}
    org = "OCA " if repos and all(r.startswith("OCA/") for r in repos) else ""
    pills = [(len(pulls), "pull requests"), (sum(p["merged"] is not None for p in pulls), "merged"),
             (len(repos), f"{org}repos")]
    x = x1
    for n, label in reversed(pills):
        w = (len(str(n)) + 1 + len(label)) * 7.8 + 26
        x -= w
        out.append(f'<rect x="{x:.1f}" y="40" width="{w:.1f}" height="28" rx="14" fill="none" stroke="{t["line"]}"/>'
                   f'<text x="{x + 13:.1f}" y="59" font-size="13" fill="{t["muted"]}">'
                   f'<tspan font-weight="700" fill="{t["ink"]}">{n}</tspan> {label}</text>')
        x -= 8
    out.append(f'<text x="{x1}" y="100" text-anchor="end" font-size="12" fill="{t["muted"]}">'
               f'{total:,} contributions · last 52 weeks</text>')

    # the signal: grid, month ticks, area, line
    for f in (0, .5, 1):
        y = base - amp * f
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{t["grid"]}"'
                   + ('' if f == 0 else ' stroke-dasharray="3 5"') + '/>')
    prev = None
    for k, (d, _) in enumerate(weeks):
        if prev is not None and d.month != prev:
            x = pts[k][0]
            out.append(f'<line x1="{x:.1f}" y1="{base}" x2="{x:.1f}" y2="{base + 5}" stroke="{t["line"]}"/>'
                       f'<text x="{x:.1f}" y="{base + 21}" text-anchor="middle" font-size="11" fill="{t["muted"]}">{d:%b}</text>')
        prev = d.month
    out.append(f'<path d="{line} L{x1},{base} L{x0},{base} Z" fill="url(#area)"/>'
               f'<path d="{line}" fill="none" stroke="{t["merged"]}" stroke-width="2.2" stroke-linejoin="round"/>')

    k = max(range(len(weeks)), key=lambda i: weeks[i][1])
    px, py = pts[k]
    start, v = weeks[k]
    anchor = "end" if px > 900 else "start" if px < 300 else "middle"
    out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{t["merged"]}"/>'
               f'<text x="{px:.1f}" y="{py - 12:.1f}" text-anchor="{anchor}" font-size="12" fill="{t["muted"]}">'
               f'busiest week · {short(start)}–{short(start + dt.timedelta(days=6))} · '
               f'<tspan fill="{t["ink"]}" font-weight="700">{v}</tspan></text>')

    # a pulse running along the year, and today breathing at the end of it
    ex, ey = pts[-1]
    out.append(f'<circle r="3.5" fill="{t["open"]}"><animateMotion dur="9s" repeatCount="indefinite" path="{line}"/></circle>'
               f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{t["open"]}" opacity=".35">'
               f'<animate attributeName="r" values="4;11;4" dur="2.4s" repeatCount="indefinite"/>'
               f'<animate attributeName="opacity" values=".45;0;.45" dur="2.4s" repeatCount="indefinite"/></circle>'
               f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" fill="{t["open"]}"/>')

    defs = (f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{t["merged"]}" stop-opacity=".3"/>'
            f'<stop offset="1" stop-color="{t["merged"]}" stop-opacity="0"/></linearGradient>')
    alt = (f"{CFG['name']}, {CFG['role']}. A line of {total:,} contributions over the last 52 weeks, "
           f"busiest in the week of {short(start)} with {v}.")
    return svg(W, H, "".join(out), defs), alt


# ================================================================ flow: pull requests from repositories into Odoo branches

def flow_svg(t, pulls):
    work = [p for p in pulls if status(p) != "closed"]
    per_repo = Counter(p["repo"] for p in work)
    per_version = Counter(odoo_version(p) for p in work)
    repos = sorted(per_repo, key=lambda r: (-per_repo[r], r))
    versions = sorted(per_version, key=lambda v: (v == "other", float(v) if v != "other" else 0))
    U, MIN, GAP, VGAP = 9, 12, 7, 26          # px per PR, smallest repo slot, gaps
    LX, RX, BAR, TOP = 350, 950, 8, 74         # left bar x, right bar x, bar width, top margin

    slot = {r: max(MIN, per_repo[r] * U) for r in repos}
    left_h = sum(slot.values()) + GAP * (len(repos) - 1)
    right_h = sum(per_version.values()) * U + VGAP * (len(versions) - 1)
    inner = max(left_h, right_h)
    W, H = 1200, int(TOP + inner + 78)

    y, ly = TOP + (inner - left_h) / 2, {}
    for r in repos:
        ly[r] = y
        y += slot[r] + GAP
    y, ry = TOP + (inner - right_h) / 2, {}
    for v in versions:
        ry[v] = y
        y += per_version[v] * U + VGAP

    # a flow is (repo, version, status); stack them on both sides in an order that keeps crossings low
    flows = Counter((p["repo"], odoo_version(p), status(p)) for p in work)
    rank = {"merged": 0, "open": 1}
    cur = {r: ly[r] + (slot[r] - per_repo[r] * U) / 2 for r in repos}
    pos = {}
    for f in sorted(flows, key=lambda f: (repos.index(f[0]), versions.index(f[1]), rank[f[2]])):
        pos[f] = [cur[f[0]], None]
        cur[f[0]] += flows[f] * U
    cur = dict(ry)
    for f in sorted(flows, key=lambda f: (versions.index(f[1]), repos.index(f[0]), rank[f[2]])):
        pos[f][1] = cur[f[1]]
        cur[f[1]] += flows[f] * U

    xa, xb = LX + BAR, RX
    xm = (xa + xb) / 2
    bands, bars, dots = [], [], []
    lane_of = {f: 0 for f in flows}
    for f, (ya, yb) in pos.items():
        h = flows[f] * U
        col = t[f[2]]
        bands.append(f'<path d="M{xa},{ya:.1f} C{xm},{ya:.1f} {xm},{yb:.1f} {xb},{yb:.1f} L{xb},{yb + h:.1f} '
                     f'C{xm},{yb + h:.1f} {xm},{ya + h:.1f} {xa},{ya + h:.1f} Z" fill="{col}" opacity=".22"/>')
        bars.append(f'<rect x="{LX}" y="{ya:.1f}" width="{BAR}" height="{h:.1f}" fill="{col}"/>'
                    f'<rect x="{RX}" y="{yb:.1f}" width="{BAR}" height="{h:.1f}" fill="{col}"/>')
    # one dot per pull request, each in its own lane of its band
    for p in sorted(work, key=lambda p: p["url"]):
        f = (p["repo"], odoo_version(p), status(p))
        ya, yb = pos[f]
        off = (lane_of[f] + .5) * U
        lane_of[f] += 1
        rnd = random.Random(p["url"])
        dur = rnd.uniform(6.5, 9.5)
        path = f"M{xa},{ya + off:.1f} C{xm},{ya + off:.1f} {xm},{yb + off:.1f} {xb},{yb + off:.1f}"
        dots.append(f'<circle r="2.4" fill="{t[f[2]]}"><animateMotion dur="{dur:.1f}s" begin="-{rnd.uniform(0, dur):.1f}s" '
                    f'repeatCount="indefinite" path="{path}"/></circle>')

    labels = [f'<text x="{LX + BAR}" y="{TOP - 30}" text-anchor="end" font-size="11" letter-spacing="2" fill="{t["muted"]}">REPOSITORY</text>',
              f'<text x="{RX}" y="{TOP - 30}" font-size="11" letter-spacing="2" fill="{t["muted"]}">ODOO BRANCH</text>']
    for r in repos:
        cy = ly[r] + slot[r] / 2 + 4.5
        labels.append(f'<text x="{LX - 12}" y="{cy:.1f}" text-anchor="end" font-size="13" fill="{t["muted"]}">{per_repo[r]}</text>'
                      f'<text x="{LX - 40}" y="{cy:.1f}" text-anchor="end" font-size="14" fill="{t["ink"]}">'
                      f'{esc(r.split("/", 1)[1] if r.startswith("OCA/") else r)}</text>')
    for v in versions:
        cy = ry[v] + per_version[v] * U / 2 + 5
        labels.append(f'<text x="{RX + BAR + 14}" y="{cy:.1f}" font-size="16" fill="{t["ink"]}"><tspan font-weight="700">{v}</tspan>'
                      f'<tspan font-size="13" fill="{t["muted"]}">  {per_version[v]} PR{"s" if per_version[v] > 1 else ""}</tspan></text>')
    ly_ = H - 28
    labels.append(f'<g font-size="12" fill="{t["muted"]}">'
                  f'<circle cx="{LX - 200}" cy="{ly_ - 4}" r="4" fill="{t["merged"]}"/><text x="{LX - 190}" y="{ly_}">merged</text>'
                  f'<circle cx="{LX - 110}" cy="{ly_ - 4}" r="4" fill="{t["open"]}"/><text x="{LX - 100}" y="{ly_}">in review</text>'
                  f'<text x="{LX + 8}" y="{ly_}">each moving dot is one pull request</text></g>')

    alt = (f"{len(work)} pull requests flowing from {len(repos)} repositories into Odoo "
           + ", ".join(f"{v} ({per_version[v]})" for v in versions) + ".")
    return svg(W, H, "".join(bands + bars + dots + labels)), alt


# ================================================================ README

def md(text):
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)


def picture(name, alt):
    return (f'<picture>\n  <source media="(prefers-color-scheme: dark)" srcset="img/{name}-dark.svg">\n'
            f'  <img src="img/{name}-light.svg" width="100%" alt="{esc(alt).replace(chr(34), "&quot;")}">\n</picture>')


def grouped(pulls, when):
    """The same change sent to several Odoo branches becomes one row."""
    hide = [h.lower() for h in CFG["lists"].get("hide", [])]
    groups = {}
    for p in sorted(pulls, key=lambda p: p[when], reverse=True):
        versions, kinds, rest = split_title(p["title"])
        if any(h in p["title"].lower() for h in hide):
            continue
        g = groups.setdefault((p["repo"], tuple(kinds), rest),
                              {"repo": p["repo"], "kinds": kinds, "rest": rest, "date": p[when], "prs": {}})
        for v in versions or [""]:
            g["prs"].setdefault(v, p)
    return list(groups.values())


def table(groups, date_label):
    if not groups:
        return "_Nothing here right now._"
    rows = [f"| Change | Odoo | Repository | {date_label} |", "|:--|:--|:--|:--|"]
    for g in groups:
        prs = sorted(g["prs"].items(), key=lambda kv: float(kv[0] or 0))
        newest = max((p for _, p in prs), key=lambda p: p["opened"])
        module, _, what = g["rest"].partition(": ")
        if re.fullmatch(r"[a-z0-9_]+", module):
            what = what or CFG.get("notes", {}).get(module, "")
            change = f"[**{md(module)}**]({newest['url']})" + (f" · {md(what)}" if what else "")
        else:
            change = f"[{md(g['rest'])}]({newest['url']})"
        kinds = " ".join(f"`{k}`" for k in g["kinds"])
        odoo = " · ".join(f"[{v or 'PR'}]({p['url']})" for v, p in prs)
        repo = f"[{g['repo'].split('/', 1)[1]}](https://github.com/{g['repo']})"
        rows.append(f"| {kinds} {change} | {odoo} | {repo} | {short(dt.date.fromisoformat(g['date']))} |")
    return "\n".join(rows)


def build():
    calendar = json.loads((CACHE / "calendar.json").read_text(encoding="utf-8"))
    pulls = json.loads((CACHE / "pulls.json").read_text(encoding="utf-8"))
    days = sorted((dt.date.fromisoformat(d), c) for d, c in calendar.items())

    IMG.mkdir(exist_ok=True)
    alts = {}
    for name, draw in (("header", lambda t: header_svg(t, days, pulls)), ("flow", lambda t: flow_svg(t, pulls))):
        for theme, t in THEMES.items():
            doc, alts[name] = draw(t)
            (IMG / f"{name}-{theme}.svg").write_text(doc, encoding="utf-8")

    lists = CFG["lists"]
    today = dt.datetime.now(dt.timezone.utc).date()
    readme = string.Template((HERE / "README.tpl.md").read_text(encoding="utf-8")).substitute(
        header=picture("header", alts["header"]),
        flow=picture("flow", alts["flow"]),
        in_review=table(grouped([p for p in pulls if status(p) == "open"], "opened")[:lists["in_review"]], "Opened"),
        merged=table(grouped([p for p in pulls if p["merged"]], "merged")[:lists["merged"]], "Merged"),
        synced=f"{today.day} {today:%b %Y}",
    )
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="build from profile/cache, without fetching")
    if not parser.parse_args().offline:
        fetch()
    build()


if __name__ == "__main__":
    main()
