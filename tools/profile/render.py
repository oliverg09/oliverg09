#!/usr/bin/env python3
"""Draws the profile SVGs (header, contribution city, project cards) from tools/profile/data/.

Standard library only. Every random choice is seeded, and each day's building is seeded
by its date, so the same data always gives the same picture and buildings keep their look.
"""
import datetime as dt
import html
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
ASSETS = HERE.parent.parent / "assets"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

MONO = "'JetBrains Mono','SF Mono',SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
INK, BODY, MUTED = "#eef1fb", "#c3c9e0", "#868ca8"
CYAN, AMBER, GOLD, RED = "#7fe3f0", "#ffd27a", "#ffc46b", "#ff5a6a"
FACADES = ["#3a4a7a", "#40598a", "#4a4280", "#33607a", "#514a86", "#2f4f6f"]
GROUND = "#1c2244"
DEFS = ('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0a0e22"/>'
        '<stop offset=".6" stop-color="#17173a"/><stop offset="1" stop-color="#2a1f48"/></linearGradient>'
        '<radialGradient id="glow"><stop offset="0" stop-color="#a77bff" stop-opacity=".32"/>'
        '<stop offset="1" stop-color="#a77bff" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="halo"><stop offset="0" stop-color="#fff3c4" stop-opacity=".3"/>'
        '<stop offset="1" stop-color="#fff3c4" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="trail"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity=".9"/></linearGradient>')
STYLE = ("@keyframes tw{0%,100%{opacity:1}50%{opacity:.15}}.tw{animation:tw 4s ease-in-out infinite}"
         "@keyframes bl{0%,55%{opacity:1}60%,100%{opacity:.12}}.bl{animation:bl 1.8s linear infinite}"
         "@keyframes shoot{0%{transform:translate(0,0);opacity:0}2%{opacity:1}"
         "9%,100%{transform:translate(280px,105px);opacity:0}}.mt{animation:shoot 11s linear infinite}")


# ---------------------------------------------------------------- data

def load():
    cal = json.loads((DATA / "calendar.json").read_text(encoding="utf-8"))
    days = sorted((dt.date.fromisoformat(d), c) for d, c in cal.items())
    return days, json.loads((DATA / "pulls.json").read_text(encoding="utf-8"))


def kept(pulls):
    """Merged or still open: the pull requests that are part of the work."""
    return [p for p in pulls if p["merged"] or p["state"] == "open"]


def versions_of(pulls):
    return sorted({v for p in pulls for v in re.findall(r"\[(\d+\.0)\]", p["title"])}, key=float)


def summarize(days, pulls):
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    best_day, best = max(days, key=lambda x: x[1])
    work = kept(pulls)
    return {
        "total": sum(c for _, c in days),
        "active": sum(1 for _, c in days if c),
        "best_day": best_day.isoformat(),
        "best": best,
        "longest": longest,
        "pulls": len(pulls),
        "merged": sum(p["merged"] for p in pulls),
        "repos": len({p["repo"] for p in work}),
        "versions": versions_of(work),
    }


def weeks(days):
    """Columns of GitHub's calendar: weeks starting on Sunday."""
    cols = []
    for d, c in days:
        if not cols or d.weekday() == 6:
            cols.append([])
        cols[-1].append((d, c))
    return cols


def months(days):
    rows = {}
    for d, c in days:
        rows.setdefault((d.year, d.month), []).append((d, c))
    return list(rows.items())


def fmt_day(d):
    return f"{d:%b} {d.day}"


def esc(text):
    return html.escape(text, quote=False)


# ---------------------------------------------------------------- drawing helpers

def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f"<style>{STYLE}</style><defs>{DEFS}</defs>{body}</svg>\n")


def shade(hex_, f):
    r, g, b = (int(hex_[k:k + 2], 16) for k in (1, 3, 5))
    cl = lambda v: max(0, min(255, round(v * f)))
    return f"#{cl(r):02x}{cl(g):02x}{cl(b):02x}"


def pts(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def poly(points, fill, extra=""):
    return f'<polygon points="{pts(points)}" fill="{fill}"{extra}/>'


def stars(rnd, w, h, n):
    return "".join(f'<circle cx="{rnd.uniform(0, w):.0f}" cy="{rnd.uniform(0, h):.0f}" r="{rnd.uniform(.4, 1.1):.1f}" '
                   f'fill="#fff" opacity="{rnd.uniform(.15, .6):.2f}"/>' for _ in range(n))


def moon(x, y, r):
    return (f'<circle cx="{x}" cy="{y}" r="{r * 3.2:.0f}" fill="url(#halo)"/>'
            f'<mask id="crescent"><rect x="{x - r - 2}" y="{y - r - 2}" width="{2 * r + 4}" height="{2 * r + 4}" fill="#fff"/>'
            f'<circle cx="{x + r * .42:.1f}" cy="{y - r * .28:.1f}" r="{r * .9:.1f}" fill="#000"/></mask>'
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="#f6eccb" mask="url(#crescent)"/>')


def meteor(x, y):
    return (f'<g class="mt"><line x1="{x - 54}" y1="{y - 20}" x2="{x}" y2="{y}" stroke="url(#trail)" '
            f'stroke-width="1.6" stroke-linecap="round"/></g>')


def box(x, y, a, h, col):
    """An isometric box: (x, y) is its front bottom corner, a its half width on screen, h its height."""
    left = [(x - a, y - a / 2), (x, y), (x, y - h), (x - a, y - a / 2 - h)]
    right = [(x, y), (x + a, y - a / 2), (x + a, y - a / 2 - h), (x, y - h)]
    top = [(x, y - h), (x - a, y - a / 2 - h), (x, y - a - h), (x + a, y - a / 2 - h)]
    return poly(left, col) + poly(right, shade(col, .64)) + poly(top, shade(col, 1.42))


def windows(x, y, a, h, rnd, lit=.5):
    """Lit windows on both visible faces of a box, one path per colour and face."""
    face = [lambda u, z: (x - a + u * a, y - a / 2 + u * a / 2 - z),
            lambda u, z: (x + u * a, y - u * a / 2 - z)]
    cols = [(.16, .4), (.6, .84)] if a < 14 else [(.12, .3), (.41, .59), (.7, .88)]
    paths, twinkle = {}, []
    for f in range(int((h - 7) // 7.5)):
        z0 = 4.5 + f * 7.5
        for side in (0, 1):
            for u0, u1 in cols:
                if rnd.random() > lit:
                    continue
                roll = rnd.random()
                col = CYAN if roll < .14 else "#fff1d6" if roll < .2 else AMBER
                P = face[side]
                quad = [P(u0, z0), P(u1, z0), P(u1, z0 + 3.4), P(u0, z0 + 3.4)]
                if rnd.random() < .05:
                    twinkle.append(poly(quad, col, f' class="tw" style="animation-delay:-{rnd.uniform(0, 4):.1f}s"'))
                else:
                    paths.setdefault((col, side), []).append("M" + "L".join(f"{px:.1f},{py:.1f}" for px, py in quad) + "Z")
    dim = ' opacity=".7"'
    out = [f'<path d="{"".join(d)}" fill="{col}"{dim if side else ""}/>' for (col, side), d in paths.items()]
    return "".join(out + twinkle)


def building(x, y, a, h, col, rnd, lit=.5):
    """A tower on its front bottom corner (x, y). Tall ones step back once. Returns (svg, roof centre)."""
    if h > 62 and rnd.random() < .75:
        h1 = h * rnd.uniform(.55, .7)
        a2 = a * rnd.choice([.6, .7])
        x2, y2 = x, y - a / 2 + a2 / 2 - h1
        body = (box(x, y, a, h1, col) + windows(x, y, a, h1, rnd, lit)
                + box(x2, y2, a2, h - h1, col) + windows(x2, y2, a2, h - h1, rnd, lit))
        roof = (x2, y2 - a2 / 2 - (h - h1))
    else:
        body = box(x, y, a, h, col) + windows(x, y, a, h, rnd, lit)
        roof = (x, y - a / 2 - h)
    return body, roof


def antenna(roof, length, blink=False):
    x, y = roof
    light = f'<circle cx="{x:.1f}" cy="{y - length:.1f}" r="{2.2 if blink else 1.3}" fill="{RED}"'
    light += ' class="bl"/>' if blink else ' opacity=".75"/>'
    return f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y - length:.1f}" stroke="#9aa3c7" stroke-width="1"/>' + light


# ---------------------------------------------------------------- the city

ORIGIN = (236, 196, 32, 16)  # x and y of the back corner, tile width and height


def iso(i, j, z=0):
    ox, oy, tw, th = ORIGIN
    return ox + (i - j) * tw / 2, oy + (i + j) * th / 2 - z


def slab(i, j, col):
    N, E, S, W = iso(i, j), iso(i + 1, j), iso(i + 1, j + 1), iso(i, j + 1)
    down = lambda p: (p[0], p[1] + 7)
    return (poly([W, S, down(S), down(W)], shade(col, .7)) + poly([S, E, down(E), down(S)], shade(col, .52))
            + poly([N, E, S, W], col))


def height(c, top):
    return 8 + 150 * (c / top) ** .6


def render_city(days, s):
    W, H = 1200, 720
    top = s["best"]
    best_day = dt.date.fromisoformat(s["best_day"])
    # (week, weekday with Sunday = 0, date, count), back to front
    cells = sorted(((i, (d.weekday() + 1) % 7, d, c) for i, col in enumerate(weeks(days)) for d, c in col),
                   key=lambda t: (t[0] + t[1], t[0]))

    out = [f'<rect width="{W}" height="{H}" rx="16" fill="url(#sky)"/>',
           f'<ellipse cx="700" cy="560" rx="560" ry="230" fill="url(#glow)"/>',
           stars(random.Random(7), W, 300, 70), moon(430, 84, 22), meteor(560, 60)]

    for i, j, d, c in cells:
        district = shade(GROUND, 1.22 if d.month % 2 else 1)
        out.append(slab(i, j, shade(district, 1.04 if (i + j) % 2 else .96)))

    prev = None
    for i, col in enumerate(weeks(days)):
        first = col[0][0]
        if first.month != prev and i < len(weeks(days)) - 1:
            x, y = iso(i + .3, 7)
            label = f"{first:%b}"
            out.append(f'<text x="{x:.1f}" y="{y + 24:.1f}" transform="rotate(26.57 {x:.1f} {y + 24:.1f})" '
                       f'font-family="{MONO}" font-size="12" letter-spacing="1.5" fill="{MUTED}">{label}</text>')
        prev = first.month

    m = .16
    for i, j, d, c in cells:
        if not c:
            continue
        rnd = random.Random(d.toordinal())
        x, y = iso(i + 1 - m, j + 1 - m)
        h = height(c, top)
        body, roof = building(x, y, (1 - 2 * m) * ORIGIN[2] / 2, h, rnd.choice(FACADES), rnd)
        out.append(body)
        if d == best_day:
            out.append(antenna(roof, 14, blink=True))
            tx, ty = roof[0], roof[1] - 16
            sign, anchor = (1, "start") if tx < 880 else (-1, "end")
            out.append(f'<path d="M{tx:.1f},{ty - 6:.1f} L{tx + sign * 34:.1f},{ty - 40:.1f} H{tx + sign * 236:.1f}" '
                       f'fill="none" stroke="{GOLD}" stroke-width="1"/>'
                       f'<text x="{tx + sign * 38:.1f}" y="{ty - 47:.1f}" text-anchor="{anchor}" font-family="{MONO}" '
                       f'font-size="14" fill="{GOLD}">tallest tower · {fmt_day(d)} · {c}</text>')
        elif h > 46 and rnd.random() < .5:
            out.append(antenna(roof, 8))

    lines = [f'<tspan fill="{CYAN}" font-weight="700">{s["total"]:,}</tspan> contributions · last 365 days',
             f'{s["active"]} buildings · one per active day',
             f'longest streak: {s["longest"]} days in a row']
    out.append(f'<g font-family="{MONO}" font-size="21" fill="{BODY}" text-anchor="end">'
               f'<text x="1150" y="72" font-size="14" letter-spacing="3" fill="{MUTED}">THE CONTRIBUTION CITY</text>'
               + "".join(f'<text x="1150" y="{114 + k * 34}">{ln}</text>' for k, ln in enumerate(lines)) + "</g>")

    out.append(f'<text x="40" y="676" font-family="{MONO}" font-size="15" fill="{MUTED}">quiet day</text>')
    for k, hh in enumerate([14, 28, 46, 70]):
        body, _ = building(146 + k * 30, 684, 9, hh, FACADES[k], random.Random(k), lit=.6)
        out.append(body)
    out.append(f'<text x="268" y="676" font-family="{MONO}" font-size="15" fill="{MUTED}">release day</text>')
    return svg(W, H, "".join(out))


# ---------------------------------------------------------------- header

def render_header(days, s):
    W, H = 1200, 330
    stats = [f'<tspan fill="{CYAN}">{s["pulls"]}</tspan> pull requests',
             f'<tspan fill="{CYAN}">{s["merged"]}</tspan> merged',
             f'<tspan fill="{CYAN}">{s["repos"]}</tspan> repositories']
    if s["versions"]:
        v = s["versions"]
        stats.append(f'Odoo <tspan fill="{CYAN}">{v[0]}</tspan>' + (f' → <tspan fill="{CYAN}">{v[-1]}</tspan>' if len(v) > 1 else ""))
    out = [f'<rect width="{W}" height="{H}" rx="16" fill="url(#sky)"/>',
           f'<ellipse cx="960" cy="330" rx="330" ry="170" fill="url(#glow)"/>',
           stars(random.Random(1), W, 210, 50), moon(1112, 66, 20), meteor(380, 40),
           f'<text x="64" y="84" font-family="{MONO}" font-size="16" letter-spacing="4" fill="{MUTED}">HI, I\'M</text>',
           f'<text x="60" y="152" font-family="{SANS}" font-size="64" font-weight="800" fill="{INK}">'
           f'{esc(CONFIG["name"])}</text>',
           f'<text x="64" y="196" font-family="{MONO}" font-size="22" fill="{BODY}">{esc(CONFIG["role"])}</text>',
           f'<text x="64" y="236" font-family="{MONO}" font-size="16" font-style="italic" fill="{MUTED}">'
           f'“{esc(CONFIG["tagline"])}”</text>',
           f'<text x="64" y="282" font-family="{MONO}" font-size="16" fill="{MUTED}">{" · ".join(stats)}</text>',
           f'<rect x="748" y="296" width="430" height="7" rx="3.5" fill="{shade(GROUND, 1.2)}"/>']

    # one tower per month of the last year, as tall as that month's contributions
    rows = months(days)[-12:]
    peak = max(sum(c for _, c in r) for _, r in rows) or 1
    for k, ((yr, mo), r) in enumerate(rows):
        total = sum(c for _, c in r)
        x = 776 + k * 33
        rnd = random.Random(yr * 12 + mo)
        body, roof = building(x, 298, 11, 16 + 150 * (total / peak) ** .6, rnd.choice(FACADES), rnd)
        out.append(body)
        if total == peak:
            out.append(antenna(roof, 12, blink=True))
        out.append(f'<text x="{x}" y="318" text-anchor="middle" font-family="{MONO}" font-size="11" '
                   f'fill="{MUTED}">{dt.date(yr, mo, 1):%b}</text>')
    return svg(W, H, "".join(out))


# ---------------------------------------------------------------- project cards

def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return lines + [cur] if cur else lines


def repo_facts(repo, pulls):
    mine = [p for p in kept(pulls) if p["repo"] == repo]
    mods = []
    for p in reversed(mine):  # oldest first, so the modules read in the order they were built
        m = re.search(r"\]\s*([a-z][a-z0-9_]+)\s*(?::|$)", p["title"])
        if m and m.group(1) not in mods:
            mods.append(m.group(1))
    merged = sum(p["merged"] for p in mine)
    stat = " · ".join(t for t in [f"{merged} merged" if merged else "",
                                  f"{len(mine) - merged} open" if len(mine) > merged else ""] if t)
    return stat, mods, versions_of(mine)


def card_layout(item, pulls, W, f):
    """Everything but the frame and the footer. Returns the parts and the y where the content ends."""
    org, name = item["repo"].split("/")
    stat, mods, _ = repo_facts(item["repo"], pulls)
    pad, cw = 36, f * .6
    parts = [f'<text x="{pad}" y="{pad + f * 1.5:.0f}" font-family="{MONO}" font-size="{f * 1.5:.0f}">'
             f'<tspan fill="{MUTED}">{esc(org)} / </tspan><tspan fill="{INK}" font-weight="800">{esc(name)}</tspan></text>']
    y = pad + f * 1.5 + f * 1.9
    # the PR count sits right of the title when both fit, otherwise on its own line below
    if (len(f"{org} / {name}") * 1.5 + len(stat) * .85) * cw + 24 < W - 2 * pad:
        parts.append(f'<text x="{W - pad}" y="{pad + f * 1.3:.0f}" text-anchor="end" font-family="{MONO}" '
                     f'font-size="{f * .85:.0f}" fill="{CYAN}">{stat}</text>')
    else:
        parts.append(f'<text x="{pad}" y="{y - f * .3:.0f}" font-family="{MONO}" font-size="{f * .85:.0f}" '
                     f'fill="{CYAN}">{stat}</text>')
        y += f * 1.5
    for line in wrap(item["text"], int((W - 2 * pad) / cw)):
        parts.append(f'<text x="{pad}" y="{y:.0f}" font-family="{MONO}" font-size="{f}" fill="{BODY}">{esc(line)}</text>')
        y += f * 1.45
    y += f * .9
    x, cf = pad, f * .8
    for mod in mods:
        w = len(mod) * cf * .6 + 22
        if x + w > W - pad:
            x, y = pad, y + cf * 2.1
        parts.append(f'<rect x="{x:.0f}" y="{y - cf * 1.15:.0f}" width="{w:.0f}" height="{cf * 1.6:.0f}" rx="8" '
                     f'fill="#232a55"/><text x="{x + 11:.0f}" y="{y:.0f}" font-family="{MONO}" font-size="{cf:.0f}" '
                     f'fill="#a8ecf5">{esc(mod)}</text>')
        x += w + 9
    return parts, y + cf * .6


def card_svg(item, pulls, W, H, f, parts):
    pad = 36
    _, _, versions = repo_facts(item["repo"], pulls)
    odoo = [f"Odoo {versions[0]}" + (f" → {versions[-1]}" if len(versions) > 1 else "")] if versions else []
    footer = " · ".join(odoo + item.get("tags", []))
    rnd = random.Random(item["repo"])
    skyline = "".join(building(W - pad - 6 - k * f * .95, H - pad + 10, f * .38, f * hh, rnd.choice(FACADES), rnd, .6)[0]
                      for k, hh in enumerate([1.1, 2.2, 1.5]))
    return svg(W, H, "".join([
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="url(#sky)" stroke="#343a66"/>',
        *parts,
        f'<text x="{pad}" y="{H - pad + 6}" font-family="{MONO}" font-size="{f * .8:.0f}" fill="{MUTED}">{esc(footer)}</text>',
        skyline,
    ]))


def render_cards(pulls):
    """The first featured project gets a full-width card, the rest go in pairs at half width."""
    feat = CONFIG["featured"]
    cards = {}
    hero = feat[0]
    parts, end = card_layout(hero, pulls, 1200, 22)
    cards[hero["repo"]] = card_svg(hero, pulls, 1200, int(end + 88), 22, parts)
    rest = feat[1:]
    for k in range(0, len(rest), 2):
        pair = rest[k:k + 2]
        laid = [card_layout(item, pulls, 600, 19) for item in pair]
        h = int(max(end for _, end in laid) + 88)
        for item, (parts, _) in zip(pair, laid):
            cards[item["repo"]] = card_svg(item, pulls, 600, h, 19, parts)
    return cards


def main():
    days, pulls = load()
    s = summarize(days, pulls)
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "header.svg").write_text(render_header(days, s), encoding="utf-8")
    (ASSETS / "city.svg").write_text(render_city(days, s), encoding="utf-8")
    for repo, doc in render_cards(pulls).items():
        (ASSETS / f"card-{repo.split('/')[1]}.svg").write_text(doc, encoding="utf-8")
    (DATA / "stats.json").write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s))


if __name__ == "__main__":
    main()
