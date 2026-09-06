#!/usr/bin/env python3
"""Generates assets/terminal.svg, the looping animated terminal on the profile README.

The `ls -t ~/projects` output is pulled from the GitHub API at build time, so
it follows what is actually public instead of going stale. The SVG itself is
pure SVG + SMIL: no scripts, no external fonts, no network at render time, so
it animates when GitHub serves it as an <img>. Every base attribute holds the
finished screen, so a renderer that ignores SMIL shows the end state rather
than an empty box.

    python3 assets/terminal.py             # fetch repos, rewrite assets/terminal.svg
    python3 assets/terminal.py --offline   # reuse the list embedded in the current SVG
    python3 assets/terminal.py --out FILE

Exit 0 on success, and on API failure (the existing SVG is left untouched or
rebuilt from its own embedded list). Exit 1 only when there is nothing at all
to build from.
"""
import argparse
import json
import math
import os
import random
import re
import sys
import tempfile
import urllib.request
import xml.dom.minidom
from pathlib import Path

# =============================================================================
# WHICH REPOS APPEAR IN `ls -t ~/projects`
#
# Automatic rule: public repos owned by USER, not forks, not archived, newest
# push first, as many as fit in MAX_LS_ROWS rows of `ls -C` style columns.
# Edit the two lists below and re-run; the daily workflow does the same.
# =============================================================================

USER = "KieranK07"

# Never shown, whatever the API says.
DENYLIST = {
    "KieranK07",                    # this profile repo
    "KieranK07.github.io",          # source for chadnerd.lol
    "pcb-business-card",            # fab files for a modified template, not a project
    "Office-Hours",                 # coursework
    "courses-degree-path-builder",  # coursework, superseded by class-royale
    "seedreset-template-1.21.11",   # minecraft template
    "loupe",                        # until it's finished
}

# If this is non-empty it is used exactly as written, in this order, and the
# API is not consulted. Manual override for when the automatic list is wrong.
ALLOWLIST = [
    # "backquest", "Nexus", "notables",
]

MAX_LS_ROWS = 4      # oldest-pushed repos are dropped until the listing fits
MIN_PROJECTS = 3     # fewer than this from the API is treated as a failed fetch

# =============================================================================
# Look and feel
# =============================================================================

W = 1200
PAD_X = 36
TITLE_H = 56
TOP = 112            # baseline of the first line
LH = 34              # line height
FS = 23              # font size
CW = 13.8            # character advance; textLength pins every string to it
AVAIL_CHARS = int((W - 2 * PAD_X) / CW)
FONT = "'JetBrains Mono','SF Mono',SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

GREEN, MINT, WHITE, DIM, MID = "#3DFD7D", "#8FE6AC", "#D8FFE8", "#17773B", "#23C85C"
PROMPT_USER, PROMPT_TAIL = "kieran@machine", ":~$"
PROMPT = PROMPT_USER + PROMPT_TAIL     # typed text starts one cell after it

HOLD = 5.0           # finished screen stays this long before it clears
GAP = 0.7            # dark gap after the clear, before the loop restarts
BLINK_ON, BLINK_OFF = 0.55, 0.45

API_BASE = os.environ.get("TERMINAL_API_BASE", "https://api.github.com")


def log(msg):
    print(f"terminal.py: {msg}", file=sys.stderr)


# ----------------------------------------------------------------------------
# project list
# ----------------------------------------------------------------------------
def fetch_repos():
    """Every repo owned by USER, as the API returns it. Raises on any problem."""
    url = f"{API_BASE}/users/{USER}/repos?per_page=100&sort=pushed&type=owner"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{USER}-profile-terminal",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos = []
    for _ in range(5):                                   # pagination guard
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as resp:
            page = json.load(resp)
            link = resp.headers.get("Link", "")
        if not isinstance(page, list):
            raise ValueError(f"unexpected payload: {type(page).__name__}")
        repos.extend(page)
        nxt = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if not nxt:
            break
        url = nxt.group(1)
    return repos


def select_projects(repos):
    """Newest push first, minus forks, archives, private repos and the denylist."""
    keep = []
    for r in repos:
        if not isinstance(r, dict) or not r.get("name") or not r.get("pushed_at"):
            continue
        if r.get("fork") or r.get("archived") or r.get("private") or r.get("disabled"):
            continue
        if r["name"] in DENYLIST:
            continue
        keep.append(r)
    keep.sort(key=lambda r: r["pushed_at"], reverse=True)
    return [r["name"] for r in keep]


def names_from_svg(path):
    """The ordered list a previous build embedded in the SVG, or []."""
    try:
        doc = xml.dom.minidom.parse(str(path))
    except Exception:
        return []
    for g in doc.getElementsByTagName("g"):
        if g.getAttribute("id") == "ls":
            return [s for s in g.getAttribute("data-projects").split(",") if s]
    return []


# ----------------------------------------------------------------------------
# ls layout
# ----------------------------------------------------------------------------
def ls_layout(names, avail=AVAIL_CHARS, max_rows=MAX_LS_ROWS):
    """Column-major like `ls -C`: each column as wide as its longest entry plus
    two spaces, using the fewest rows that fit in `avail` characters.
    Returns (rows, column_widths), or None if max_rows is not enough."""
    n = len(names)
    for rows in range(1, max_rows + 1):
        cols = math.ceil(n / rows)
        widths = [max(len(s) for s in names[c * rows:(c + 1) * rows]) + 2 for c in range(cols)]
        widths[-1] -= 2                                   # no padding after the last column
        if sum(widths) <= avail:
            return rows, widths
    return None


def fit(names, avail=AVAIL_CHARS, max_rows=MAX_LS_ROWS):
    """Longest prefix of `names` whose listing fits. Returns (shown, layout)."""
    for n in range(len(names), 0, -1):
        layout = ls_layout(names[:n], avail, max_rows)
        if layout:
            return names[:n], layout
    return [], None


def ls_rows(names, layout):
    """[(name, x offset in characters), ...] per rendered row."""
    rows, widths = layout
    offsets = [sum(widths[:c]) for c in range(len(widths))]
    out = []
    for r in range(rows):
        row = []
        for c in range(len(widths)):
            i = c * rows + r
            if i < len(names):
                row.append((names[i], offsets[c]))
        out.append(row)
    return out


# ----------------------------------------------------------------------------
# svg
# ----------------------------------------------------------------------------
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def build_svg(names, layout):
    random.seed(2029)                                     # jitter is deterministic per input

    script = [
        ("cmd", "whoami"),
        ("out", "kieran", WHITE),
        ("out", "offsec · systems · embedded · ai", MINT),
        ("blank",),
        ("cmd", "ls -t ~/projects"),
        ("ls", ls_rows(names, layout)),
        ("blank",),
        ("cmd", "make"),
        ("build", "building"),
    ]

    # -- timeline -------------------------------------------------------------
    t, line = 0.4, 0
    elements, cur_x, cur_y, cur_win = [], [], [], []

    def baseline(i):
        return TOP + i * LH

    def cursor_top(y):
        return round(y - FS * 0.82, 1)

    for item in script:
        kind, y = item[0], baseline(line)
        if kind == "cmd":
            cmd = item[1]
            x0 = round(PAD_X + (len(PROMPT) + 1) * CW, 1)
            elements.append(dict(type="prompt", y=y, t_on=t))
            cur_x.append((t, x0))
            cur_y.append((t, cursor_top(y)))
            t_type = t + (0.9 if line == 0 else 0.6)
            cur_win.append((t, t_type, "blink"))
            steps, tt = [], t_type
            for k, ch in enumerate(cmd, 1):
                tt += random.uniform(0.055, 0.14) + (0.05 if ch == " " else 0)
                steps.append((tt, k))
                cur_x.append((tt, round(x0 + k * CW, 1)))
            cur_win.append((t_type, tt, "solid"))
            t_enter = tt + random.uniform(0.25, 0.4)
            cur_win.append((tt, t_enter, "blink"))
            elements.append(dict(type="typed", text=cmd, x=x0, y=y, steps=steps, color=WHITE))
            t = t_enter + 0.10
            cur_win.append((t_enter, t, "hidden"))
            line += 1
        elif kind == "out":
            elements.append(dict(type="print", text=item[1], y=y, t_on=t, color=item[2]))
            t += 0.045
            line += 1
        elif kind == "blank":
            line += 1
        elif kind == "ls":
            rows = []
            for cells in item[1]:
                rows.append(dict(cells=cells, y=baseline(line), t_on=t))
                t += 0.045
                line += 1
            elements.append(dict(type="ls", rows=rows))
        elif kind == "build":
            word = item[1]
            elements.append(dict(type="print", text=word, y=y, t_on=t, color=GREEN))
            xd = round(PAD_X + len(word) * CW, 1)
            cur_x.append((t, xd))
            cur_y.append((t, cursor_top(y)))
            steps, tt = [], t
            for k in range(1, 4):
                tt += 0.38
                steps.append((tt, k))
                cur_x.append((tt, round(xd + k * CW, 1)))
            elements.append(dict(type="typed", text="...", x=xd, y=y, steps=steps, color=GREEN))
            cur_win.append((t, None, "blink"))            # closed at T_CLEAR below
            t = tt
            line += 1

    T_CLEAR = t + HOLD
    CYCLE = T_CLEAR + GAP
    cur_win = [(a, T_CLEAR if b is None else b, m) for a, b, m in cur_win]
    H = baseline(line - 1) + 44

    # -- SMIL helpers --------------------------------------------------------
    def keyframes(events):
        ev = sorted(events, key=lambda e: e[0])
        out, last = [], -1.0
        for tt, v in ev:
            k = round(tt / CYCLE, 4)
            if k <= last:
                k = round(last + 0.0001, 4)
            out.append((k, v))
            last = k
        assert out[0][0] == 0, "first keyTime must be 0"
        if out[-1][0] < 1:
            out.append((1.0, out[-1][1]))
        return ";".join(num(v) for _, v in out), ";".join(f"{k:.4f}" for k, _ in out)

    def anim(attr, events):
        vals, kts = keyframes(events)
        return (f'<animate attributeName="{attr}" calcMode="discrete" values="{vals}" '
                f'keyTimes="{kts}" dur="{CYCLE:.2f}s" repeatCount="indefinite"/>')

    def show_hide(t_on):
        return anim("opacity", [(0, 0), (t_on, 1), (T_CLEAR, 0)])

    def cursor_opacity():
        ev = [(0.0, 0)]
        for a, b, mode in cur_win:
            if mode == "solid":
                ev.append((a, 1))
            elif mode == "hidden":
                ev.append((a, 0))
            else:
                tt, on = a, True
                while tt < b:
                    ev.append((tt, 1 if on else 0))
                    tt += BLINK_ON if on else BLINK_OFF
                    on = not on
        ev.append((T_CLEAR, 0))
        return ev

    def text(x, y, s, fill=None, extra=""):
        f = f' fill="{fill}"' if fill else ""
        return (f'<text x="{x}" y="{y}"{f} textLength="{len(s) * CW:.1f}" '
                f'lengthAdjust="spacingAndGlyphs">{esc(s)}{extra}</text>')

    # -- emit ----------------------------------------------------------------
    defs = [
        '<linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0" stop-color="#0a120c"/><stop offset="1" stop-color="#071009"/></linearGradient>',
        f'<linearGradient id="roll" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{GREEN}" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="{GREEN}" stop-opacity="0.075"/>'
        f'<stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient>',
        '<radialGradient id="vig" cx="0.5" cy="0.5" r="0.78">'
        '<stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity="0.5"/></radialGradient>',
        '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="2" fill="#000" fill-opacity="0.16"/></pattern>',
        '<filter id="glow" x="-4%" y="-8%" width="108%" height="116%">'
        '<feGaussianBlur stdDeviation="1.6" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        f'<clipPath id="win"><rect width="{W}" height="{H}" rx="18"/></clipPath>',
    ]
    body = [
        f'<rect width="{W}" height="{H}" rx="18" fill="url(#bg)" stroke="{DIM}"/>',
        f'<g clip-path="url(#win)"><rect width="{W}" height="{TITLE_H}" fill="#0d1b11"/>'
        f'<rect y="{TITLE_H}" width="{W}" height="1" fill="{DIM}"/></g>',
    ]
    for cx, col in ((36, GREEN), (60, MID), (84, DIM)):
        body.append(f'<circle cx="{cx}" cy="28" r="7" fill="{col}"/>')
    body.append(f'<text x="{W // 2}" y="34" text-anchor="middle" fill="{DIM}" font-size="15">kieran@machine: ~</text>')

    screen = []
    for n, e in enumerate(elements):
        if e["type"] == "prompt":
            screen.append(
                f'<text x="{PAD_X}" y="{e["y"]}" textLength="{len(PROMPT) * CW:.1f}" lengthAdjust="spacingAndGlyphs">'
                f'<tspan fill="{GREEN}">{PROMPT_USER}</tspan><tspan fill="{MINT}">{esc(PROMPT_TAIL)}</tspan>'
                f'{show_hide(e["t_on"])}</text>')
        elif e["type"] == "print":
            screen.append(text(PAD_X, e["y"], e["text"], e["color"], show_hide(e["t_on"])))
        elif e["type"] == "ls":
            rows = "".join(
                f'<g>' + "".join(text(f"{PAD_X + off * CW:.1f}", row["y"], name) for name, off in row["cells"])
                + show_hide(row["t_on"]) + "</g>"
                for row in e["rows"])
            screen.append(f'<g id="ls" fill="{GREEN}" data-projects="{esc(",".join(names))}">{rows}</g>')
        elif e["type"] == "typed":
            s, x, y = e["text"], e["x"], e["y"]
            full = len(s) * CW
            width_ev = [(0, 0)] + [(tt, round(k * CW + 2, 1)) for tt, k in e["steps"]] + [(T_CLEAR, 0)]
            defs.append(f'<clipPath id="c{n}"><rect x="{x - 1}" y="{y - FS}" width="{full + 2:.1f}" '
                        f'height="{FS * 1.4:.1f}">{anim("width", width_ev)}</rect></clipPath>')
            screen.append(f'<text x="{x}" y="{y}" fill="{e["color"]}" textLength="{full:.1f}" '
                          f'lengthAdjust="spacingAndGlyphs" clip-path="url(#c{n})">{esc(s)}</text>')

    fx, fy = cur_x[-1][1], cur_y[-1][1]                   # cursor rests where it ends up
    cur_x.insert(0, (0.0, cur_x[0][1]))
    cur_y.insert(0, (0.0, cur_y[0][1]))
    screen.append(f'<rect x="{fx}" y="{fy}" width="{CW}" height="{FS * 1.05:.1f}" fill="{GREEN}" '
                  f'shape-rendering="crispEdges">{anim("x", cur_x)}{anim("y", cur_y)}'
                  f'{anim("opacity", cursor_opacity())}</rect>')
    body.append('<g filter="url(#glow)">' + "".join(screen) + '</g>')

    body.append(f'<g clip-path="url(#win)">'
                f'<rect x="0" y="-160" width="{W}" height="160" fill="url(#roll)">'
                f'<animate attributeName="y" from="-160" to="{H}" dur="7s" repeatCount="indefinite"/></rect>'
                f'<rect y="{TITLE_H + 1}" width="{W}" height="{H - TITLE_H - 1}" fill="url(#scan)"/>'
                f'<rect y="{TITLE_H + 1}" width="{W}" height="{H - TITLE_H - 1}" fill="url(#vig)"/>'
                f'</g>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-label="terminal" font-family="{FONT}" font-size="{FS}">'
            f'<defs>{"".join(defs)}</defs>{"".join(body)}</svg>\n')


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=Path(__file__).with_name("terminal.svg"), type=Path)
    ap.add_argument("--offline", action="store_true", help="skip the API; reuse the list in the current SVG")
    args = ap.parse_args()

    previous = names_from_svg(args.out)
    if ALLOWLIST:
        names, source = list(dict.fromkeys(ALLOWLIST)), "ALLOWLIST"
    elif args.offline:
        names, source = previous, "existing svg (--offline)"
    else:
        try:
            names = select_projects(fetch_repos())
            if len(names) < MIN_PROJECTS:
                raise ValueError(f"only {len(names)} usable repos in the response")
            source = "github api"
        except Exception as e:                            # network, HTTP, JSON, shape
            log(f"github api unavailable ({e}); keeping the existing list")
            names, source = previous, "existing svg (api failed)"

    too_long = [n for n in names if len(n) > AVAIL_CHARS]
    names = [n for n in names if n not in too_long]
    if too_long:
        log(f"skipping names wider than the terminal: {', '.join(too_long)}")
    if not names:
        log("no project list from any source; not writing")
        return 1

    shown, layout = fit(names)
    svg = build_svg(shown, layout)
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.out.parent, delete=False)
    with tmp:
        tmp.write(svg)
    os.replace(tmp.name, args.out)                        # never leave a truncated SVG behind

    rows, _ = layout
    log(f"{source}: {len(names)} candidates, showing {len(shown)} in {rows} row(s): {', '.join(shown)}")
    if len(shown) < len(names):
        log(f"not shown (older pushes): {', '.join(names[len(shown):])}")
    log(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
