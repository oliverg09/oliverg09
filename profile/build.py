#!/usr/bin/env python3
"""Builds this profile: reads my activity on GitHub, draws img/aquarium.svg and writes README.md.

    python profile/build.py             fetch from GitHub, then build
    python profile/build.py --offline   build from profile/cache only

Edit profile/README.tpl.md (text) and profile/profile.toml (settings), never README.md.
Standard library only, Python 3.11+.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import string
import tomllib
from pathlib import Path

import activity
import aquarium

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "profile"
CACHE = HERE / "cache"
CFG = tomllib.loads((HERE / "profile.toml").read_text(encoding="utf-8"))


def md(text):
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)


def short(day):
    d = dt.date.fromisoformat(day)
    return f"{d:%b} {d.day}"


def split_title(title):
    """'[18.0][ADD] module: what' -> (['18.0'], ['ADD'], 'module: what')"""
    tags, rest = re.match(r"((?:\[[^\]]*\]\s*)*)(.*)", title).groups()
    tags = re.findall(r"\[([^\]]*)\]", tags)
    is_version = lambda t: re.fullmatch(r"\d+\.0", t)
    return [t for t in tags if is_version(t)], [t for t in tags if not is_version(t)], rest


def grouped(pulls, when):
    """The same change sent to several Odoo branches becomes one row."""
    hide = [h.lower() for h in CFG["lists"].get("hide", [])]
    groups = {}
    for p in sorted(pulls, key=lambda p: p[when], reverse=True):
        if any(h in p["title"].lower() for h in hide):
            continue
        versions, kinds, rest = split_title(p["title"])
        g = groups.setdefault((p["repo"], tuple(kinds), rest),
                              {"repo": p["repo"], "kinds": kinds, "rest": rest, "date": p[when], "prs": {}})
        for v in versions or [""]:
            g["prs"].setdefault(v, p)
    return list(groups.values())


def table(groups, date_label):
    if not groups:
        return "_Nothing here right now._"
    rows = [f"| | Change | Odoo | Repository | {date_label} |", "|:-:|:--|:--|:--|:--|"]
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
        emoji = aquarium.SPECIES[aquarium.species(newest)][2]
        rows.append(f"| {emoji} | {kinds} {change} | {odoo} | {repo} | {short(g['date'])} |")
    return "\n".join(rows)


def reef(pulls):
    count = {}
    for p in pulls:
        if p["merged"] or p["state"] == "open":
            count[p["repo"]] = count.get(p["repo"], 0) + 1
    return " · ".join(f"[{r.split('/', 1)[1]}](https://github.com/{r}/pulls?q=is%3Apr+author%3A{CFG['user']}) <sup>{n}</sup>"
                      for r, n in sorted(count.items(), key=lambda kv: (-kv[1], kv[0])))


def build():
    calendar = json.loads((CACHE / "calendar.json").read_text(encoding="utf-8"))
    pulls = json.loads((CACHE / "pulls.json").read_text(encoding="utf-8"))
    user = json.loads((CACHE / "user.json").read_text(encoding="utf-8"))
    days = sorted((dt.date.fromisoformat(d), c) for d, c in calendar.items())

    svg, alt, info = aquarium.draw(days, pulls, user["created"], html.escape(CFG["name"]), html.escape(CFG["role"]))
    (ROOT / "img").mkdir(exist_ok=True)
    (ROOT / "img" / "aquarium.svg").write_text(svg, encoding="utf-8")

    today = dt.datetime.now(dt.timezone.utc).date()
    lists = CFG["lists"]
    readme = string.Template((HERE / "README.tpl.md").read_text(encoding="utf-8")).substitute(
        aquarium=f'<img src="img/aquarium.svg" width="100%" alt="{html.escape(alt)}">',
        arrivals=table(grouped([p for p in pulls if p["merged"]], "merged")[:lists["arrivals"]], "Merged"),
        quarantine=table(grouped([p for p in pulls if status_open(p)], "opened")[:lists["quarantine"]], "Opened"),
        reef=reef(pulls),
        upcoming=f"Next in the tank: {info['upcoming']}." if info["upcoming"] else "Every decoration is unlocked.",
        synced=f"{today.day} {today:%b %Y}",
    )
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


def status_open(p):
    return p["state"] == "open" and not p["merged"]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="build from profile/cache, without fetching")
    if not parser.parse_args().offline:
        activity.fetch(CFG["user"], os.environ.get("GITHUB_TOKEN"), CACHE)
    build()


if __name__ == "__main__":
    main()
