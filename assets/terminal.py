#!/usr/bin/env python3
"""Generates terminal.svg: a looping animated terminal session.

Pure SVG + SMIL. No scripts, no external fonts, no network, so it animates when
GitHub serves it through its image proxy. Every base attribute holds the
finished screen, so a renderer that ignores SMIL just shows the end state.

    python3 assets/terminal.py > assets/terminal.svg
"""
import random

random.seed(2029)

W = 1200
PAD_X = 36
TITLE_H = 56
TOP = 112            # baseline of the first line
LH = 34              # line height
FS = 23              # font size
CW = 13.8            # character advance; textLength pins every line to it
FONT = "'JetBrains Mono','SF Mono',SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

GREEN, MINT, WHITE, DIM, MID = "#3DFD7D", "#8FE6AC", "#D8FFE8", "#17773B", "#23C85C"
PROMPT_USER, PROMPT_TAIL = "kieran@machine", ":~$"
PROMPT = PROMPT_USER + PROMPT_TAIL     # typed text starts one cell after it
COLW = 19                              # ls column width, in characters

# No run of spaces anywhere: HTML parsers ignore xml:space, and textLength
# would stretch a collapsed string. Columns are positioned explicitly instead.
SCRIPT = [
    ("cmd", "whoami"),
    ("out", "kieran", WHITE),
    ("out", "offsec · systems · embedded · ai", MINT),
    ("blank",),
    ("cmd", "ls -t ~/projects"),
    # same projects, same order as the table in README.md
    ("cols", ["backquest", "Nexus", "notables", "swarf"], GREEN),
    ("cols", ["claudeyes", "class-royale", "roomba-controller", "authoritative-fps"], GREEN),
    ("cols", ["doordle"], GREEN),
    ("blank",),
    ("cmd", "make"),
    ("build", "building"),
]
HOLD = 5.0           # finished screen stays this long before it clears
GAP = 0.7            # dark gap after the clear, before the loop restarts
BLINK_ON, BLINK_OFF = 0.55, 0.45


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


# ---------------------------------------------------------------- timeline
t = 0.4
line = 0
elements = []        # drawn things
cur_x, cur_y = [], []  # (time, value) events for the cursor
cur_win = []         # (start, end, "blink"|"solid"|"hidden")


def baseline(i):
    return TOP + i * LH


def cursor_top(y):
    return round(y - FS * 0.82, 1)


for item in SCRIPT:
    kind = item[0]
    y = baseline(line)
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
    elif kind == "cols":
        elements.append(dict(type="cols", names=item[1], y=y, t_on=t, color=item[2]))
        t += 0.045
        line += 1
    elif kind == "blank":
        line += 1
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
        cur_win.append((t, None, "blink"))   # open-ended; closed at T_CLEAR
        t = tt
        line += 1

T_CLEAR = t + HOLD
CYCLE = T_CLEAR + GAP
cur_win = [(a, T_CLEAR if b is None else b, m) for a, b, m in cur_win]
H = baseline(line - 1) + 44


# ---------------------------------------------------------------- animation helpers
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


# ---------------------------------------------------------------- emit
defs, body = [], []
defs.append(f'<linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0" stop-color="#0a120c"/><stop offset="1" stop-color="#071009"/></linearGradient>')
defs.append(f'<linearGradient id="roll" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0" stop-color="{GREEN}" stop-opacity="0"/>'
            f'<stop offset="0.5" stop-color="{GREEN}" stop-opacity="0.075"/>'
            f'<stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient>')
defs.append('<radialGradient id="vig" cx="0.5" cy="0.5" r="0.78">'
            '<stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0.5"/></radialGradient>')
defs.append('<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
            '<rect width="4" height="2" fill="#000" fill-opacity="0.16"/></pattern>')
defs.append('<filter id="glow" x="-4%" y="-8%" width="108%" height="116%">'
            '<feGaussianBlur stdDeviation="1.6" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
defs.append(f'<clipPath id="win"><rect width="{W}" height="{H}" rx="18"/></clipPath>')

# window
body.append(f'<rect width="{W}" height="{H}" rx="18" fill="url(#bg)" stroke="{DIM}"/>')
body.append(f'<g clip-path="url(#win)"><rect width="{W}" height="{TITLE_H}" fill="#0d1b11"/>'
            f'<rect y="{TITLE_H}" width="{W}" height="1" fill="{DIM}"/></g>')
for cx, col in ((36, GREEN), (60, MID), (84, DIM)):
    body.append(f'<circle cx="{cx}" cy="28" r="7" fill="{col}"/>')
body.append(f'<text x="{W // 2}" y="34" text-anchor="middle" fill="{DIM}" font-size="15">kieran@machine: ~</text>')

# screen text
screen = []
for n, e in enumerate(elements):
    y = e["y"]
    if e["type"] == "prompt":
        tl = len(PROMPT) * CW
        screen.append(f'<text x="{PAD_X}" y="{y}" textLength="{tl:.1f}" lengthAdjust="spacingAndGlyphs">'
                      f'<tspan fill="{GREEN}">{PROMPT_USER}</tspan><tspan fill="{MINT}">{esc(PROMPT_TAIL)}</tspan>'
                      f'{show_hide(e["t_on"])}</text>')
    elif e["type"] == "print":
        s = e["text"]
        screen.append(f'<text x="{PAD_X}" y="{y}" fill="{e["color"]}" textLength="{len(s) * CW:.1f}" '
                      f'lengthAdjust="spacingAndGlyphs">{esc(s)}{show_hide(e["t_on"])}</text>')
    elif e["type"] == "cols":
        cells = "".join(
            f'<text x="{PAD_X + i * COLW * CW:.1f}" y="{y}" textLength="{len(name) * CW:.1f}" '
            f'lengthAdjust="spacingAndGlyphs">{esc(name)}</text>'
            for i, name in enumerate(e["names"]))
        screen.append(f'<g fill="{e["color"]}">{cells}{show_hide(e["t_on"])}</g>')
    elif e["type"] == "typed":
        s, x = e["text"], e["x"]
        full = len(s) * CW
        cid = f"c{n}"
        width_ev = [(0, 0)] + [(tt, round(k * CW + 2, 1)) for tt, k in e["steps"]] + [(T_CLEAR, 0)]
        defs.append(f'<clipPath id="{cid}"><rect x="{x - 1}" y="{y - FS}" width="{full + 2:.1f}" '
                    f'height="{FS * 1.4:.1f}">{anim("width", width_ev)}</rect></clipPath>')
        screen.append(f'<text x="{x}" y="{y}" fill="{e["color"]}" textLength="{full:.1f}" '
                      f'lengthAdjust="spacingAndGlyphs" clip-path="url(#{cid})">{esc(s)}</text>')

# cursor: base position is where it ends up
fx, fy = cur_x[-1][1], cur_y[-1][1]
cur_x.insert(0, (0.0, cur_x[0][1]))
cur_y.insert(0, (0.0, cur_y[0][1]))
screen.append(f'<rect x="{fx}" y="{fy}" width="{CW}" height="{FS * 1.05:.1f}" fill="{GREEN}" shape-rendering="crispEdges">'
              f'{anim("x", cur_x)}{anim("y", cur_y)}{anim("opacity", cursor_opacity())}</rect>')

body.append('<g filter="url(#glow)">' + "".join(screen) + '</g>')

# CRT overlays
body.append(f'<g clip-path="url(#win)">'
            f'<rect x="0" y="-160" width="{W}" height="160" fill="url(#roll)">'
            f'<animate attributeName="y" from="-160" to="{H}" dur="7s" repeatCount="indefinite"/></rect>'
            f'<rect y="{TITLE_H + 1}" width="{W}" height="{H - TITLE_H - 1}" fill="url(#scan)"/>'
            f'<rect y="{TITLE_H + 1}" width="{W}" height="{H - TITLE_H - 1}" fill="url(#vig)"/>'
            f'</g>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'role="img" aria-label="terminal" font-family="{FONT}" font-size="{FS}">'
       f'<defs>{"".join(defs)}</defs>{"".join(body)}</svg>\n')
print(svg, end="")
