#!/usr/bin/env python3
"""Rewrites the generated blocks of README.md (between <!-- name:start --> and <!-- name:end -->)."""
import datetime as dt
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
README = HERE.parent.parent / "README.md"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
ICONS = {"merged": "🟣", "open": "🟢", "closed": "⚪"}


def md(text):
    return re.sub(r"([\\`*\[\]<>])", r"\\\1", text)


def replace_block(text, name, content):
    pattern = re.compile(rf"(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README.md has no <!-- {name}:start/end --> markers")
    return pattern.sub(lambda m: m.group(1) + content + "\n" + m.group(2), text)


def city(s):
    best = dt.date.fromisoformat(s["best_day"])
    alt = (f"Contribution city: an isometric skyline at night with one building per active day of the last year. "
           f"{s['total']:,} contributions, {s['active']} buildings, the tallest on {best:%b} {best.day} with {s['best']}.")
    return f'<img src="./assets/city.svg" width="100%" alt="{alt}">'


def state(p):
    return "merged" if p["merged"] else p["state"]


def split_title(title):
    """'[18.0][ADD] module: what' -> (['18.0'], ['ADD'], 'module: what')"""
    tags, rest = re.match(r"((?:\[[^\]]*\]\s*)*)(.*)", title).groups()
    tags = re.findall(r"\[([^\]]*)\]", tags)
    return [t for t in tags if re.fullmatch(r"\d+\.0", t)], [t for t in tags if not re.fullmatch(r"\d+\.0", t)], rest


def groups(pulls):
    """The same change opened for several Odoo versions becomes one line."""
    out = {}
    for p in pulls:  # newest first
        versions, kinds, rest = split_title(p["title"])
        g = out.setdefault((p["repo"], tuple(kinds), rest), {"repo": p["repo"], "kinds": kinds, "rest": rest,
                                                             "created": p["created"], "by_version": {}})
        rank = {"merged": 0, "open": 1, "closed": 2}
        for v in versions or [""]:
            have = g["by_version"].get(v)
            if not have or rank[state(p)] < rank[state(have)]:
                g["by_version"][v] = p
    return list(out.values())


def pull_line(g):
    module, _, what = g["rest"].partition(": ")
    if not what and module in CONFIG.get("module_notes", {}):
        what = CONFIG["module_notes"][module]
    label = f"**{md(module)}**: {md(what)}" if what else f"**{md(module)}**"
    prs = sorted(g["by_version"].items(), key=lambda kv: float(kv[0] or 0))
    states = {state(p) for _, p in prs}
    main = max((p for _, p in prs), key=lambda p: p["created"])
    if len(prs) == 1:
        versions = [v for v, _ in prs if v]
    else:  # each version links its own pull request, with its own colour when they differ
        versions = [(f"{ICONS[state(p)]} " if len(states) > 1 else "") + f"[{v}]({p['url']})" for v, p in prs]
    day = dt.date.fromisoformat(g["created"])
    meta = " · ".join([md(g["repo"]), *map(md, g["kinds"]), *versions, f"{day:%b} {day.day}"])
    return f"- {ICONS[state(main)]} [{label}]({main['url']}) <sub>{meta}</sub>"


def other_repos(pulls):
    featured = {f["repo"] for f in CONFIG["featured"]}
    count = {}
    for p in pulls:
        if p["merged"] and p["repo"] not in featured:
            count[p["repo"]] = count.get(p["repo"], 0) + 1
    links = [f"[{r.split('/')[1]}](https://github.com/{r}/pulls?q=is%3Apr+author%3A{CONFIG['user']})"
             for r, _ in sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))]
    return f"<sub>Also merged into {' · '.join(links)}</sub>" if links else ""


def main():
    stats = json.loads((HERE / "data/stats.json").read_text(encoding="utf-8"))
    pulls = json.loads((HERE / "data/pulls.json").read_text(encoding="utf-8"))
    latest = groups(pulls)[:CONFIG["latest_pulls"]]
    text = README.read_text(encoding="utf-8")
    text = replace_block(text, "city", city(stats))
    text = replace_block(text, "repos", other_repos(pulls))
    text = replace_block(text, "pulls", "\n".join(map(pull_line, latest)) + "\n\n<sub>🟣 merged · 🟢 open · ⚪ closed</sub>")
    README.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
