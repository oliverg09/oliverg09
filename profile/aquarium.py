"""Draws the aquarium from my GitHub activity.

    a fish        for every day with contributions in the last year
                  (a month is a school, a busier day a bigger fish)
    a creature    for every pull request, its species set by the kind of change
    a coral       for every repository, growing with the pull requests it gets
    decorations   that unlock at milestones

Every random choice is seeded by what it draws (a date, a pull request, a repository),
so the tank only changes where the data does.
"""
import datetime as dt
import math
import random
import re
from collections import Counter

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
W, H = 1200, 780
L, T, R, B = 20, 34, 1180, 600   # the water
FLOOR = 556                       # where the sand starts, give or take its waves

FISH_COLORS = ["#ff7b54", "#ffb347", "#ffd166", "#9be564", "#4ecdc4", "#48cae4",
               "#7b9cff", "#b07cf0", "#f15bb5", "#fe6d73", "#00e0c0", "#f9c74f"]  # one per month
CORAL_COLORS = ["#ff6f91", "#ff9671", "#ffc75f", "#d65db1", "#f9a8d4", "#e07a5f", "#b388eb", "#ff8fab", "#f4845f"]
KELP_COLORS = ["#2f9e5b", "#3fae6a", "#23874c", "#4caf50"]

SPECIES = {  # id: (name, what one stands for, emoji)
    "puffer": ("Pufferfish", "a new module", "🐡"),
    "turtle": ("Sea turtle", "a migration", "🐢"),
    "crab": ("Crab", "a fix", "🦀"),
    "octo": ("Octopus", "an improvement", "🐙"),
    "hermit": ("Hermit crab", "a backport", "🐚"),
    "star": ("Starfish", "any other change", "⭐"),
    "jelly": ("Jellyfish", "a PR in review", "🪼"),
}
BY_KIND = {"ADD": "puffer", "MIG": "turtle", "FIX": "crab", "IMP": "octo", "BKP": "hermit"}

UNLOCKS = [  # (decoration, what it counts, how many, name, unit)
    ("bubbler", "merged", 10, "an air stone", "merged PRs"),
    ("kelp", "merged", 25, "a kelp forest", "merged PRs"),
    ("wreck", "merged", 50, "a shipwreck", "merged PRs"),
    ("whale", "year", 1000, "a passing whale", "contributions in a year"),
    ("chest", "merged", 100, "a treasure chest", "merged PRs"),
]

STYLE = (
    ".tl{transform-box:fill-box;transform-origin:100% 50%;animation:wag .45s ease-in-out infinite alternate}"
    "@keyframes wag{from{transform:rotate(-16deg)}to{transform:rotate(16deg)}}"
    ".fa,.fb{transform-box:fill-box;animation:flap 2.4s ease-in-out infinite alternate}"
    ".fa{transform-origin:100% 100%}.fb{transform-origin:100% 0;animation-direction:alternate-reverse}"
    "@keyframes flap{from{transform:rotate(-20deg)}to{transform:rotate(16deg)}}"
    ".tn{transform-box:fill-box;transform-origin:50% 0;animation:sway 3s ease-in-out infinite alternate}"
    ".kp,.an{transform-box:fill-box;transform-origin:50% 100%;animation:sway 7s ease-in-out infinite alternate}"
    ".an{animation-duration:4s}"
    "@keyframes sway{from{transform:rotate(-5deg)}to{transform:rotate(5deg)}}"
    ".ry{animation:ray 9s ease-in-out infinite alternate}@keyframes ray{from{opacity:.3}to{opacity:1}}"
    ".sp{animation:sp 2s ease-in-out infinite}@keyframes sp{0%,100%{opacity:.15}50%{opacity:1}}"
)


# ================================================================ helpers

def kinds_of(title):
    return [t.upper() for t in re.findall(r"\[([^\]]*)\]", title) if not re.fullmatch(r"\d+\.0", t)]


def species(p):
    """Open pull requests drift around as jellyfish; merged ones become the species of their kind."""
    if not p["merged"]:
        return "jelly"
    return next((BY_KIND[k] for k in kinds_of(p["title"]) if k in BY_KIND), "star")


def shade(hex_, f):
    r, g, b = (int(hex_[k:k + 2], 16) for k in (1, 3, 5))
    cl = lambda v: max(0, min(255, round(v * f)))
    return f"#{cl(r):02x}{cl(g):02x}{cl(b):02x}"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def smooth(points):
    """A Catmull-Rom curve through the points, as cubic Béziers."""
    d = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    for k in range(len(points) - 1):
        p0, p1 = points[max(k - 1, 0)], points[k]
        p2, p3 = points[k + 1], points[min(k + 2, len(points) - 1)]
        d += (f" C{p1[0] + (p2[0] - p0[0]) / 6:.1f},{p1[1] + (p2[1] - p0[1]) / 6:.1f}"
              f" {p2[0] - (p3[0] - p1[0]) / 6:.1f},{p2[1] - (p3[1] - p1[1]) / 6:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return d


def star_path(r1, r2, n=5):
    pts = [((r1 if k % 2 == 0 else r2) * math.sin(math.pi * k / n), -(r1 if k % 2 == 0 else r2) * math.cos(math.pi * k / n))
           for k in range(2 * n)]
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"


def spikes():
    out = []
    for a in range(0, 360, 30):
        t, da = math.radians(a), math.radians(8)
        p = [(9.5 * math.cos(t - da), 9.5 * math.sin(t - da)), (13.5 * math.cos(t), 13.5 * math.sin(t)),
             (9.5 * math.cos(t + da), 9.5 * math.sin(t + da))]
        out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in p) + "Z")
    return "".join(out)


# ================================================================ the creatures, drawn once at the origin, facing right

EYE = '<circle cx="{x}" cy="{y}" r="{r}" fill="#fff"/><circle cx="{px}" cy="{y}" r="{pr}" fill="#102030"/>'


def eye(x, y, r):
    return EYE.format(x=x, y=y, r=r, px=x + r * .25, pr=r * .5)


CREATURES = {
    # fish, from a neon tetra to an angelfish; the body takes the colour of the <use>
    "f1": '<path class="tl" d="M-7,0L-13,-4.5L-13,4.5Z" fill="currentColor"/><ellipse rx="8" ry="3.6" fill="currentColor"/>'
          '<path d="M-5,-.5H5" stroke="#a8f4ff" stroke-width="1.3" stroke-linecap="round" opacity=".9"/>' + eye(4.6, -1, 1.2),
    "f2": '<path class="tl" d="M-10,0L-18,-7L-16,0L-18,7Z" fill="currentColor"/><path d="M-5,-5Q1,-11 6,-5Z" fill="currentColor" opacity=".75"/>'
          '<ellipse rx="11" ry="6" fill="currentColor"/><ellipse cx="1" cy="2.6" rx="8" ry="2.6" fill="#fff" opacity=".28"/>' + eye(6.5, -1.6, 1.8),
    "f3": '<path class="tl" d="M-13,0L-22,-8Q-19,0 -22,8Z" fill="currentColor"/><path d="M-6,-7Q0,-14 7,-7ZM-3,7Q2,12 6,7Z" fill="currentColor" opacity=".8"/>'
          '<ellipse rx="14" ry="8" fill="currentColor"/><path d="M-4,-7.6Q-1,0 -4,7.6M5,-7Q8,0 5,7" stroke="#fff" stroke-width="2.6" fill="none" opacity=".85"/>'
          + eye(9.5, -2, 2.1),
    "f4": '<path class="tl" d="M-12,0L-21,-8L-21,8Z" fill="currentColor"/><path d="M-8,-7L3,-26L9,-7ZM-8,7L3,26L9,7Z" fill="currentColor" opacity=".85"/>'
          '<ellipse rx="15" ry="11" fill="currentColor"/><path d="M-3,-10.5V10.5M5,-9.5V9.5" stroke="#102030" stroke-width="2" opacity=".22"/>'
          '<ellipse cx="2" cy="4" rx="10" ry="4" fill="#fff" opacity=".2"/>' + eye(9.5, -2.5, 2.3),
    "puffer": f'<path class="tl" d="M-10,0L-17,-5L-17,5Z" fill="#e9b949"/><path d="{spikes()}" fill="#d9a93a"/>'
              '<circle r="10.5" fill="#f4d35e"/><ellipse cy="4.5" rx="8" ry="5" fill="#fff4cf"/>'
              '<circle cx="-3" cy="-5" r="1.3" fill="#c48a1e"/><circle cx="1" cy="-7" r="1" fill="#c48a1e"/><circle cx="-6" cy="-1" r="1" fill="#c48a1e"/>'
              + eye(5, -3, 2.6) + '<path d="M9,2.5q1.5,1 0,2" stroke="#8a5a12" fill="none"/>',
    "turtle": '<g transform="rotate(30 -15 8)"><ellipse cx="-15" cy="8" rx="6" ry="2.6" fill="#8fbf7a"/></g>'
              '<g transform="rotate(-30 -15 -8)"><ellipse cx="-15" cy="-8" rx="6" ry="2.6" fill="#8fbf7a"/></g>'
              '<path class="fa" d="M6,-8Q2,-24 -12,-27Q-4,-16 -2,-7Z" fill="#8fbf7a"/><path class="fb" d="M6,8Q2,24 -12,27Q-4,16 -2,7Z" fill="#8fbf7a"/>'
              '<ellipse cx="21" rx="6.5" ry="4.8" fill="#9cc58a"/><circle cx="24" cy="-1.6" r="1.1" fill="#102030"/>'
              '<ellipse rx="17" ry="11.5" fill="#4f7d3f"/>'
              '<path d="M-6,-5L0,-8L6,-5L6,1L0,4L-6,1ZM-6,-5L-12,-3M6,-5L12,-3M-6,1L-12,3M6,1L12,3M0,4V10M0,-8V-11" '
              'stroke="#2f5426" stroke-width="1.2" fill="#5d8f4a"/><ellipse rx="17" ry="11.5" fill="none" stroke="#7aa35f" stroke-width="1.5"/>',
    "crab": '<path d="M-6,2L-12,5L-14,10M-5,4L-10,8L-11,12M6,2L12,5L14,10M5,4L10,8L11,12M-3,5L-6,10L-6,13M3,5L6,10L6,13" '
            'stroke="#c4402a" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M-6,-2L-11,-6M6,-2L11,-6M-3,-5L-3.5,-10M3,-5L3.5,-10" stroke="#c4402a" stroke-width="1.6" stroke-linecap="round"/>'
            '<circle cx="-12" cy="-8" r="3.8" fill="#e4572e"/><circle cx="12" cy="-8" r="3.8" fill="#e4572e"/>'
            '<path d="M-12,-8l-3,-3M12,-8l3,-3" stroke="#a83220" stroke-width="1.2"/>'
            '<ellipse rx="9.5" ry="6.5" fill="#e4572e"/><ellipse cy="-2" rx="6" ry="2.6" fill="#fff" opacity=".22"/>'
            + eye(-3.5, -10.5, 1.7) + eye(3.5, -10.5, 1.7),
    "octo": '<g class="tn"><path d="M-8,0q-6,8 -3,16t-4,10M-4.5,1q-3,9 0,16t-2,10M-1.5,1q-1,9 1,17t0,9M1.5,1q1,9 -1,17t1,9'
            'M4.5,1q3,9 0,16t2,10M8,0q6,8 3,16t4,10" stroke="#b5487a" stroke-width="3.2" stroke-linecap="round" fill="none"/></g>'
            '<ellipse cy="-9" rx="11" ry="13" fill="#c95b8e"/><ellipse cx="-3" cy="-15" rx="4" ry="5" fill="#fff" opacity=".18"/>'
            '<circle cx="5" cy="-14" r="1.2" fill="#a8406f"/><circle cx="-6" cy="-12" r="1" fill="#a8406f"/>'
            + eye(-4.5, -5, 2.6) + eye(4.5, -5, 2.6),
    "hermit": '<path d="M4,0L9,4M2,1L5,6M6,-5L7,-10M8,-5L10,-9" stroke="#c4402a" stroke-width="1.5" stroke-linecap="round"/>'
              '<ellipse cx="9" cy="-3" rx="4" ry="3" fill="#e4572e"/>' + eye(7, -10.5, 1.4) + eye(10, -9.5, 1.4)
              + '<path d="M-12,0C-14,-12 -4,-18 3,-12C8,-7 4,0 -2,0Z" fill="#d9a066"/>'
              '<path d="M-3,-3C-8,-3 -8,-10 -3,-11C2,-12 4,-6 0,-5C-2,-5 -3,-7 -1.5,-8" stroke="#a8723a" stroke-width="1.4" fill="none" stroke-linecap="round"/>',
    "star": f'<path d="{star_path(10, 4.4)}" fill="#ff8c42" stroke="#ff8c42" stroke-width="2.4" stroke-linejoin="round"/>'
            '<circle r="1.6" fill="#ffd0a8"/><circle cx="0" cy="-5" r=".9" fill="#ffd0a8"/><circle cx="4.5" cy="-1.5" r=".9" fill="#ffd0a8"/>'
            '<circle cx="-4.5" cy="-1.5" r=".9" fill="#ffd0a8"/><circle cx="2.8" cy="4" r=".9" fill="#ffd0a8"/><circle cx="-2.8" cy="4" r=".9" fill="#ffd0a8"/>',
    "jelly": '<circle cy="-8" r="22" fill="url(#glow)"/>'
             '<g class="tn"><path d="M-8,0q-3,8 0,14t0,12M-3,1q3,8 0,15t0,12M3,1q-3,8 0,15t0,12M8,0q3,8 0,14t0,12" '
             'stroke="#f0d4ff" stroke-width="1.4" fill="none" opacity=".75"/></g>'
             '<path d="M-12,0Q-13,-17 0,-17Q13,-17 12,0Q6,3 0,.5Q-6,3 -12,0Z" fill="#d7a6ff" opacity=".8"/>'
             '<ellipse cy="-9" rx="6" ry="4" fill="#fff" opacity=".35"/><path d="M-10,-1Q0,4 10,-1" stroke="#f7e6ff" fill="none" opacity=".8"/>',
}
SIZE = {"f1": 16, "f2": 26, "f3": 34, "f4": 42, "puffer": 28, "turtle": 50, "jelly": 30}

DEFS = (
    '<linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5ec8e5"/>'
    '<stop offset=".35" stop-color="#1f8fbf"/><stop offset="1" stop-color="#0b3b66"/></linearGradient>'
    '<radialGradient id="vignette" cx=".5" cy=".45" r=".75"><stop offset=".55" stop-color="#03182c" stop-opacity="0"/>'
    '<stop offset="1" stop-color="#03182c" stop-opacity=".55"/></radialGradient>'
    '<linearGradient id="sand" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ecd9a8"/><stop offset="1" stop-color="#b8945a"/></linearGradient>'
    '<linearGradient id="ray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".22"/>'
    '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    '<radialGradient id="glow"><stop offset="0" stop-color="#e9c6ff" stop-opacity=".45"/><stop offset="1" stop-color="#e9c6ff" stop-opacity="0"/></radialGradient>'
    '<radialGradient id="gold"><stop offset="0" stop-color="#fff3b0" stop-opacity=".8"/><stop offset="1" stop-color="#ffd166" stop-opacity="0"/></radialGradient>'
    '<linearGradient id="brass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f1d58a"/><stop offset=".45" stop-color="#d4b05a"/>'
    '<stop offset=".7" stop-color="#b8913a"/><stop offset="1" stop-color="#e0c070"/></linearGradient>'
    '<linearGradient id="cabinet" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a3846"/><stop offset="1" stop-color="#18212b"/></linearGradient>'
    f'<clipPath id="tank"><rect x="{L}" y="{T}" width="{R - L}" height="{B - T}"/></clipPath>'
    + "".join(f'<g id="{k}">{v}</g>' for k, v in CREATURES.items())
)


def swimmer(ref, x, y, scale, dx, dy, dur, begin, color=None, turn=True):
    """A creature going dx, dy and back; it turns around halfway when `turn`."""
    col = f' color="{color}"' if color else ""
    timing = f'dur="{dur:.1f}s" begin="-{begin:.1f}s" repeatCount="indefinite"'
    move = (f'<animateTransform attributeName="transform" type="translate" values="0,0;{dx:.0f},{dy:.0f};0,0" '
            f'keyTimes="0;.5;1" calcMode="spline" keySplines=".42 0 .58 1;.42 0 .58 1" {timing}/>')
    if turn:
        a, b = (scale, -scale) if dx >= 0 else (-scale, scale)
        body = (f'<g><animateTransform attributeName="transform" type="scale" values="{a:.2f},{scale:.2f};{b:.2f},{scale:.2f}" '
                f'keyTimes="0;.5" calcMode="discrete" {timing}/><use href="#{ref}"{col}/></g>')
    else:
        body = f'<g transform="scale({scale:.2f})"><use href="#{ref}"{col}/></g>'
    return f'<g transform="translate({x:.0f},{y:.0f})"><g>{move}{body}</g></g>'


def keep_inside(x, dx, lo=L + 30, hi=R - 30):
    return -dx if not lo <= x + dx <= hi else dx


# ================================================================ corals

def coral(kind, x, y, size, col, rnd):
    out = []
    if kind == "branch":
        def grow(x0, y0, ang, length, width, depth):
            x1, y1 = x0 + length * math.sin(ang), y0 - length * math.cos(ang)
            out.append(f'<path d="M{x0:.1f},{y0:.1f}L{x1:.1f},{y1:.1f}" stroke="{col}" stroke-width="{width:.1f}" stroke-linecap="round"/>')
            if depth == 0:
                out.append(f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="{width * .8:.1f}" fill="{shade(col, 1.25)}"/>')
                return
            for k in ((-1, 1) if rnd.random() < .7 else (-1, 0, 1)):
                grow(x1, y1, ang + k * rnd.uniform(.28, .55), length * rnd.uniform(.62, .8), width * .74, depth - 1)
        grow(x, y, rnd.uniform(-.1, .1), size * .34, size * .11, 3 if size < 70 else 4)
    elif kind == "fan":
        n, spread = 9 + int(size / 12), rnd.uniform(1.1, 1.5)
        tips = []
        for k in range(n):
            a, rr = -spread / 2 + spread * k / (n - 1), size * rnd.uniform(.8, 1)
            tips.append((x + rr * math.sin(a), y - rr * math.cos(a)))
        out.append(f'<path d="M{x},{y}' + "".join(f"L{px:.1f},{py:.1f}" for px, py in tips) + f'Z" fill="{col}" opacity=".3" stroke-linejoin="round"/>')
        out.append(f'<path d="' + "".join(f"M{x},{y}Q{(x + px) / 2 + rnd.uniform(-5, 5):.1f},{(y + py) / 2:.1f} {px:.1f},{py:.1f}" for px, py in tips)
                   + f'" stroke="{col}" stroke-width="2" fill="none" stroke-linecap="round"/>')
        for f in (.4, .65, .88):
            pts = [(x + (px - x) * f, y + (py - y) * f) for px, py in tips]
            out.append(f'<path d="M' + "L".join(f"{px:.1f},{py:.1f}" for px, py in pts) + f'" stroke="{col}" stroke-width="1.2" fill="none" opacity=".85"/>')
    elif kind == "brain":
        r = size * .5
        h = r * .78
        out.append(f'<path d="M{x - r:.1f},{y}A{r:.1f},{h:.1f} 0 0 1 {x + r:.1f},{y}Z" fill="{col}"/>')
        for k in range(1, 5):
            yy = y - h * k / 5
            half = r * math.sqrt(1 - (k / 5) ** 2) * .82
            pts = [(x - half + 2 * half * s / 12, yy + 2.2 * math.sin(s * 1.6 + k)) for s in range(13)]
            out.append(f'<path d="{smooth(pts)}" stroke="{shade(col, .7)}" stroke-width="1.5" fill="none"/>')
    elif kind == "tubes":
        tubes = []
        n = 3 + min(4, int(size / 28))
        for k in range(n):
            tx, th, tw = x + (k - (n - 1) / 2) * size * .16 + rnd.uniform(-2, 2), size * rnd.uniform(.45, 1), size * .14
            tubes.append((th, f'<rect x="{tx - tw / 2:.1f}" y="{y - th:.1f}" width="{tw:.1f}" height="{th:.1f}" rx="{tw / 2:.1f}" '
                              f'fill="{shade(col, rnd.uniform(.85, 1.1))}"/><ellipse cx="{tx:.1f}" cy="{y - th + tw * .4:.1f}" '
                              f'rx="{tw * .36:.1f}" ry="{tw * .2:.1f}" fill="{shade(col, .5)}"/>'))
        out += [svg for _, svg in sorted(tubes, key=lambda t: -t[0])]
    else:  # anemone
        r, n = size * .22, 12 + int(size / 8)
        tent = []
        for k in range(n):
            a, ln = -1.2 + 2.4 * k / (n - 1), size * rnd.uniform(.35, .55)
            sx, sy = x + r * .8 * math.sin(a), y - r * .9
            ex, ey = sx + ln * math.sin(a * 1.1), sy - ln * math.cos(a)
            tent.append(f"M{sx:.1f},{sy:.1f}Q{(sx + ex) / 2 + rnd.uniform(-5, 5):.1f},{(sy + ey) / 2:.1f} {ex:.1f},{ey:.1f}")
        out.append(f'<g class="an"><path d="{"".join(tent)}" stroke="{col}" stroke-width="{size * .05:.1f}" stroke-linecap="round" fill="none"/></g>'
                   f'<ellipse cx="{x:.1f}" cy="{y - r * .4:.1f}" rx="{r:.1f}" ry="{r * .7:.1f}" fill="{shade(col, .7)}"/>')
    return "".join(out)


# ================================================================ scenery

def sand():
    rnd = random.Random("sand")
    pts = [(L + k * (R - L) / 12, FLOOR + rnd.uniform(-8, 8)) for k in range(13)]
    specks = "".join(f'<circle cx="{rnd.uniform(L, R):.0f}" cy="{rnd.uniform(FLOOR + 10, B):.0f}" r="{rnd.uniform(.6, 1.6):.1f}" '
                     f'fill="{rnd.choice(["#a07c48", "#fff4d6", "#8c6d3f"])}" opacity=".6"/>' for _ in range(140))
    return f'<path d="{smooth(pts)}L{R},{B}L{L},{B}Z" fill="url(#sand)"/>' + specks


def rays():
    rnd = random.Random("rays")
    out = []
    for k in range(5):
        x0, w, skew = rnd.uniform(80, 1080), rnd.uniform(30, 80), rnd.uniform(60, 160)
        out.append(f'<polygon class="ry" style="animation-delay:-{rnd.uniform(0, 9):.1f}s" points="{x0:.0f},{T} {x0 + w:.0f},{T} '
                   f'{x0 + w + skew + 40:.0f},{FLOOR} {x0 + skew - 20:.0f},{FLOOR}" fill="url(#ray)"/>')
    return "".join(out)


def rocks():
    rnd = random.Random("rocks")
    out = []
    for _ in range(6):
        x, y, w, h = rnd.uniform(60, 1140), rnd.uniform(566, 580), rnd.uniform(34, 80), rnd.uniform(16, 36)
        col = rnd.choice(["#5b6670", "#4d5761", "#66717c"])
        out.append(f'<path d="M{x - w / 2:.1f},{y:.1f}C{x - w / 2:.1f},{y - h * .8:.1f} {x - w * .2:.1f},{y - h:.1f} {x + w * .05:.1f},{y - h:.1f}'
                   f'C{x + w * .35:.1f},{y - h:.1f} {x + w / 2:.1f},{y - h * .6:.1f} {x + w / 2:.1f},{y:.1f}Z" fill="{col}"/>'
                   f'<ellipse cx="{x - w * .12:.1f}" cy="{y - h * .72:.1f}" rx="{w * .18:.1f}" ry="{h * .14:.1f}" fill="#fff" opacity=".15"/>')
    return "".join(out)


def kelp(n, seed):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        x, y, h = rnd.uniform(40, 1160), rnd.uniform(560, 578), rnd.uniform(90, 250)
        seg, wob = h / 4, rnd.uniform(8, 16)
        d = f"M{x:.0f},{y:.0f}q{wob:.0f},{-seg / 2:.0f} 0,{-seg:.0f}" + f"t0,{-seg:.0f}" * 3
        out.append(f'<path class="kp" style="animation-delay:-{rnd.uniform(0, 7):.1f}s" d="{d}" stroke="{rnd.choice(KELP_COLORS)}" '
                   f'stroke-width="{rnd.uniform(4, 8):.1f}" stroke-linecap="round" fill="none" opacity=".9"/>')
    return "".join(out)


def bubbles(x, n, seed, stone=True):
    rnd = random.Random(seed)
    out = [f'<rect x="{x - 9}" y="{B - 14}" width="18" height="8" rx="4" fill="#7b8794"/>'] if stone else []
    for _ in range(n):
        r, dur = rnd.uniform(1.6, 4.4), rnd.uniform(5, 9)
        x0 = x + rnd.uniform(-4, 4)
        timing = f'dur="{dur:.1f}s" begin="-{rnd.uniform(0, dur):.1f}s" repeatCount="indefinite"'
        out.append(f'<circle cx="{x0:.0f}" cy="{B - 16}" r="{r:.1f}" fill="#dff7ff" fill-opacity=".15" stroke="#e8fbff" stroke-opacity=".75">'
                   f'<animate attributeName="cy" values="{B - 16};{T + 8}" {timing}/>'
                   f'<animate attributeName="cx" values="{x0:.0f};{x0 + 7:.0f};{x0 - 5:.0f};{x0 + 3:.0f}" {timing}/></circle>')
    return "".join(out)


def whale():
    body = ("M130,0C120,-30 60,-42 -10,-38C-70,-34 -110,-18 -140,-6L-176,-28C-180,-14 -178,-2 -172,6L-178,26L-140,8"
            "C-100,26 -40,40 30,36C80,34 118,22 130,0Z")
    return (f'<g opacity=".5"><g><animateTransform attributeName="transform" type="translate" values="-260,150;1480,120" begin="-30s" '
            f'dur="80s" repeatCount="indefinite"/><path d="{body}" fill="#0c2f4f"/>'
            '<path d="M20,18Q10,40 -14,44Q0,30 4,16Z" fill="#0a2843"/><circle cx="96" cy="2" r="2.5" fill="#06192b"/></g></g>')


def wreck(x, y):
    return (f'<g transform="translate({x},{y}) rotate(-8)" opacity=".92">'
            '<path d="M-30,-56L-46,-160M-50,-128L-14,-136" stroke="#3b2a1f" stroke-width="6" stroke-linecap="round"/>'
            '<path d="M-125,0L-110,-50L95,-58L128,-20L112,0Z" fill="#4a3426"/>'
            '<path d="M-112,-42L104,-49M-118,-24L118,-30M-121,-10L120,-14" stroke="#5e4433" stroke-width="2"/>'
            + "".join(f'<circle cx="{px}" cy="-30" r="6" fill="#16242e" stroke="#8a6a3c" stroke-width="2"/>' for px in (-70, -30, 10, 50))
            + '<path d="M-90,-50q-4,-14 3,-24M60,-56q5,-12 -2,-22" stroke="#2f9e5b" stroke-width="3" fill="none" stroke-linecap="round"/></g>')


def chest(x, y):
    coins = "".join(f'<circle cx="{x + dx}" cy="{y - 22 + dy}" r="3" fill="#ffd166" stroke="#c99a2e"/>'
                    for dx, dy in ((-8, 0), (-2, -3), (5, -1), (10, 1), (1, 2)))
    return (f'<circle cx="{x}" cy="{y - 24}" r="34" fill="url(#gold)" class="sp"/>'
            f'<path d="M{x - 22},{y - 22}L{x - 18},{y - 44}L{x + 26},{y - 40}L{x + 22},{y - 22}Z" fill="#6b4320"/>'
            f'<rect x="{x - 22}" y="{y - 22}" width="44" height="22" rx="2" fill="#8b5a2b"/>' + coins
            + f'<path d="M{x - 22},{y - 12}H{x + 22}M{x},{y - 22}V{y}" stroke="#e9c46a" stroke-width="3"/>')


# ================================================================ the tank

def draw(days, pulls, created, name, role):
    year = days[-365:]
    total = sum(c for _, c in year)
    active = [(d, c) for d, c in year if c]
    work = [p for p in pulls if p["merged"] or p["state"] == "open"]
    merged = sum(1 for p in pulls if p["merged"])
    metrics = {"merged": merged, "year": total}
    unlocked = {u[0] for u in UNLOCKS if metrics[u[1]] >= u[2]}
    locked = [u for u in UNLOCKS if u[0] not in unlocked]
    upcoming = max(locked, key=lambda u: metrics[u[1]] / u[2]) if locked else None

    # ---- corals: one per repository, placed in the order I first contributed, so old corals keep their spot
    per_repo = Counter(p["repo"] for p in work)
    first = {}
    for p in work:
        first[p["repo"]] = min(first.get(p["repo"], p["opened"]), p["opened"])
    corals, taken = [], []
    for repo in sorted(per_repo, key=lambda r: (first[r], r)):
        rnd = random.Random(repo)
        x = rnd.uniform(70, 1130)
        for _ in range(12):
            if all(abs(x - t) > 62 for t in taken):
                break
            x = rnd.uniform(70, 1130)
        taken.append(x)
        size = 40 + 26 * math.sqrt(per_repo[repo])
        kind = rnd.choice(["branch", "branch", "fan", "tubes", "brain", "anemone"])
        corals.append((rnd.uniform(562, 584), x, repo, coral(kind, x, 0, size, rnd.choice(CORAL_COLORS), rnd)))
    corals.sort()
    biggest = sorted(per_repo, key=lambda r: (-per_repo[r], r))[:4]

    # ---- creatures: one per pull request
    floor, swim = [], []
    for p in work:
        sp = species(p)
        rnd = random.Random(p["url"])
        if sp in ("crab", "hermit", "star"):
            x, y = rnd.uniform(50, 1150), rnd.uniform(574, 590)
            if sp == "crab":
                dx = keep_inside(x, rnd.choice([-1, 1]) * rnd.uniform(20, 70))
                floor.append((y, swimmer("crab", x, y, rnd.uniform(.7, .9), dx, 0, rnd.uniform(6, 12), rnd.uniform(0, 12), turn=False)))
            elif sp == "hermit":
                dx = keep_inside(x, rnd.choice([-1, 1]) * rnd.uniform(15, 40))
                floor.append((y, swimmer("hermit", x, y, rnd.uniform(.9, 1.1), dx, 0, rnd.uniform(14, 20), rnd.uniform(0, 20))))
            else:
                floor.append((y, f'<use href="#star" transform="translate({x:.0f},{y + 4:.0f}) rotate({rnd.uniform(0, 72):.0f}) scale(.9)"/>'))
        elif sp == "octo":
            x, y = rnd.uniform(80, 1120), rnd.uniform(522, 540)
            floor.append((y, swimmer("octo", x, y, .9, rnd.uniform(-10, 10), -16, rnd.uniform(5, 8), rnd.uniform(0, 8), turn=False)))
        elif sp == "turtle":
            x, y = rnd.uniform(250, 950), rnd.uniform(150, 420)
            dx = keep_inside(x, rnd.choice([-1, 1]) * rnd.uniform(200, 380))
            swim.append((SIZE["turtle"], swimmer("turtle", x, y, rnd.uniform(.9, 1.1), dx, rnd.uniform(-30, 30), rnd.uniform(34, 50), rnd.uniform(0, 50))))
        elif sp == "puffer":
            x, y = rnd.uniform(100, 1100), rnd.uniform(120, 470)
            dx = keep_inside(x, rnd.choice([-1, 1]) * rnd.uniform(60, 160))
            swim.append((SIZE["puffer"], swimmer("puffer", x, y, 1, dx, rnd.uniform(-15, 15), rnd.uniform(14, 22), rnd.uniform(0, 22))))
        else:  # jellyfish
            x, y = rnd.uniform(80, 1120), rnd.uniform(90, 300)
            swim.append((SIZE["jelly"], swimmer("jelly", x, y, rnd.uniform(.9, 1.15), rnd.uniform(-25, 25), -rnd.uniform(30, 60),
                                                 rnd.uniform(10, 16), rnd.uniform(0, 16), turn=False)))

    # ---- fish: one per active day; a month swims as one school, a busier day is a bigger fish
    top = max((c for _, c in active), default=1)
    schools = {}
    for d, c in active:
        if (d.year, d.month) not in schools:
            sr = random.Random(f"school-{d.year}-{d.month}")
            schools[d.year, d.month] = {"x": sr.uniform(140, 1060), "y": sr.uniform(110, 450), "dir": sr.choice([-1, 1]),
                                        "dist": sr.uniform(60, 150), "dy": sr.uniform(-15, 15), "dur": sr.uniform(11, 18),
                                        "begin": sr.uniform(0, 18)}
        s = schools[d.year, d.month]
        rnd = random.Random(d.toordinal())
        level = 1 + min(3, int(4 * math.sqrt(c / top)))
        x, y = clamp(s["x"] + rnd.gauss(0, 70), 50, 1150), clamp(s["y"] + rnd.gauss(0, 38), 70, 500)
        dx = keep_inside(x, s["dir"] * s["dist"] * rnd.uniform(.85, 1.15))
        swim.append((SIZE[f"f{level}"], swimmer(f"f{level}", x, y, rnd.uniform(.85, 1.1), dx, s["dy"], s["dur"] * rnd.uniform(.94, 1.06),
                                                s["begin"] + rnd.uniform(0, .8), FISH_COLORS[d.month - 1])))
    swim.sort(key=lambda t: t[0])  # small ones further back

    # ---- the scene, back to front
    scene = [f'<rect x="{L}" y="{T}" width="{R - L}" height="{B - T}" fill="url(#water)"/>', rays()]
    if "whale" in unlocked:
        scene.append(whale())
    scene += [sand(), kelp(6, "kelp")]
    if "kelp" in unlocked:
        scene.append(kelp(12, "forest"))
    scene.append(rocks())
    if "wreck" in unlocked:
        scene.append(wreck(930, 574))
    if "chest" in unlocked:
        scene.append(chest(1080, 588))
    scene += [f'<g transform="translate(0,{y:.0f})">{c}</g>' for y, _, _, c in corals]
    scene += [s for _, s in sorted(floor, key=lambda t: t[0])]
    if "bubbler" in unlocked:
        scene.append(bubbles(random.Random("stone").uniform(200, 1000), 14, "stone"))
    scene.append("".join(bubbles(random.Random(f"b{k}").uniform(60, 1140), 2, f"b{k}", stone=False) for k in range(4)))
    scene += [f'<text x="{x:.0f}" y="{min(y + 16, 596):.0f}" text-anchor="middle" font-family="{MONO}" font-size="11" font-weight="700" '
              f'fill="#4a3a20" stroke="#f3e3b8" stroke-width="3.5" stroke-linejoin="round" paint-order="stroke">'
              f'{repo.split("/", 1)[-1]}</text>' for y, x, repo, _ in corals if repo in biggest]
    scene += [s for _, s in swim]
    scene += [f'<rect x="{L}" y="{T}" width="{R - L}" height="{B - T}" fill="url(#vignette)"/>',
              f'<g><animateTransform attributeName="transform" type="translate" values="0,0;-80,0" dur="6s" repeatCount="indefinite"/>'
              f'<path d="M{L - 80},{T + 6}' + "".join(f"q20,-5 40,0t40,0" for _ in range(17)) + f'V{T}H{L - 80}Z" fill="#e8fbff" opacity=".3"/></g>',
              f'<polygon points="{L + 40},{T} {L + 130},{T} {L + 50},{B} {L},{B} {L},{T + 80}" fill="#fff" opacity=".05"/>',
              f'<rect x="{R - 34}" y="{T}" width="3" height="{B - T}" fill="#fff" opacity=".08"/>']

    tank = (f'<g clip-path="url(#tank)">{"".join(scene)}</g>'
            f'<rect x="{L}" y="{T}" width="{R - L}" height="{B - T}" fill="none" stroke="#9ec9dc" stroke-opacity=".5" stroke-width="2"/>'
            f'<rect x="12" y="20" width="1176" height="16" rx="5" fill="#1f2a36"/><rect x="{L}" y="{T + 2}" width="{R - L}" height="3" fill="#e8fbff" opacity=".45"/>'
            f'<rect x="12" y="596" width="1176" height="14" rx="4" fill="#1f2a36"/>')

    # ---- the cabinet: a brass plaque and the species guide
    counts = Counter(species(p) for p in work)
    guide = [("fish", "Fish", "an active day", len(active)), ("coral", "Coral", "a repository", len(per_repo))]
    guide += [(sp, *SPECIES[sp][:2], counts[sp]) for sp in ("puffer", "turtle", "crab", "octo", "hermit", "star", "jelly") if counts[sp]]
    cols = math.ceil(len(guide) / 2)
    colw = 710 / cols
    icons = {"fish": '<use href="#f3" color="#ff7b54" transform="translate({x},{y}) scale(.72)"/>',
             "puffer": '<use href="#puffer" transform="translate({x},{y}) scale(.85)"/>',
             "turtle": '<use href="#turtle" transform="translate({x},{y}) scale(.5)"/>',
             "crab": '<use href="#crab" transform="translate({x},{y}) scale(.8)"/>',
             "octo": '<use href="#octo" transform="translate({x},{y2}) scale(.62)"/>',
             "hermit": '<use href="#hermit" transform="translate({x},{y2}) scale(.85)"/>',
             "star": '<use href="#star" transform="translate({x},{y}) scale(.85)"/>',
             "jelly": '<use href="#jelly" transform="translate({x},{y2}) scale(.68)"/>'}
    legend = [f'<text x="446" y="640" font-family="{SANS}" font-size="11" font-weight="600" letter-spacing="2.5" fill="#8fa3b8">WHO LIVES HERE</text>']
    for k, (sp, title, means, n) in enumerate(guide):
        x, y = 446 + (k % cols) * colw, 676 + (k // cols) * 52
        ix, iy = x + 16, y - 5
        if sp == "coral":
            legend.append(coral("branch", ix, iy + 15, 30, "#ff6f91", random.Random("legend")))
        else:
            legend.append(icons[sp].format(x=f"{ix:.0f}", y=f"{iy:.0f}", y2=f"{iy + 4:.0f}"))
        legend.append(f'<text x="{x + 38:.0f}" y="{y - 4:.0f}" font-family="{SANS}" font-size="13" font-weight="600" fill="#e6edf3">'
                      f'{title} <tspan fill="#7fd3e8">{n}</tspan></text>'
                      f'<text x="{x + 38:.0f}" y="{y + 12:.0f}" font-family="{SANS}" font-size="11" fill="#8fa3b8">{means}</text>')

    founded = dt.date.fromisoformat(created)
    if upcoming:
        key, metric, need, label, unit = upcoming
        have = metrics[metric]
        progress = (f'<text x="64" y="728" font-family="{SANS}" font-size="11.5" fill="#4a3716">Next: {label} at {need:,} {unit} · {have:,}/{need:,}</text>'
                    f'<rect x="64" y="736" width="330" height="6" rx="3" fill="#7a5a1c" opacity=".3"/>'
                    f'<rect x="64" y="736" width="{330 * have / need:.0f}" height="6" rx="3" fill="#4a3716" opacity=".75"/>')
    else:
        progress = f'<text x="64" y="732" font-family="{SANS}" font-size="11.5" fill="#4a3716">Every decoration unlocked. Keep swimming.</text>'
    screws = "".join(f'<circle cx="{sx}" cy="{sy}" r="3.2" fill="#a07d33" stroke="#7a5a1c"/>'
                     f'<path d="M{sx - 2},{sy}H{sx + 2}" stroke="#6b4e17"/>' for sx in (54, 406) for sy in (636, 746))
    plaque = (f'<rect x="44" y="626" width="372" height="130" rx="6" fill="url(#brass)" stroke="#9c7a34"/>{screws}'
              f'<text x="64" y="664" font-family="{SANS}" font-size="23" font-weight="800" letter-spacing="2.5" fill="#3a2a0f">{name.upper()}</text>'
              f'<text x="64" y="686" font-family="{SANS}" font-size="13" fill="#4a3716">{role}</text>'
              f'<text x="64" y="706" font-family="{SANS}" font-size="11.5" font-style="italic" fill="#5c4520">'
              f'Reef founded {founded:%b %Y} · {total:,} contributions this year</text>' + progress)

    cabinet = (f'<rect x="24" y="606" width="1152" height="164" rx="12" fill="url(#cabinet)"/>'
               f'<rect x="24" y="606" width="1152" height="2" fill="#3c4d5f"/>' + plaque + "".join(legend))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           f"<style>{STYLE}</style><defs>{DEFS}</defs>{tank}{cabinet}</svg>\n")
    alt = (f"{name}'s GitHub as an aquarium: {len(active)} fish, one per day with contributions in the last year; "
           f"{len(work)} creatures, one per pull request; {len(per_repo)} corals, one per repository.")
    info = {"upcoming": upcoming and f"{upcoming[3]} at {upcoming[2]:,} {upcoming[4]} ({metrics[upcoming[1]]:,} so far)"}
    return svg, alt, info
