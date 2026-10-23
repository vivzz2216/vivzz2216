#!/usr/bin/env python3
"""
build.py -- generates every SVG in ./assets from scratch.

    python scripts/build.py           # art only (uses assets/data.json if it exists)
    python scripts/build.py --live    # pull fresh numbers from the GitHub API first

Why this exists
  * GitHub renders SVGs inside <img>, where web fonts and scripts cannot load.
    So all text is converted to vector paths using the bundled fonts (scripts/fonts,
    SIL OFL) and looks identical on every OS and browser.
  * Animation is pure declarative SMIL, which GitHub allows.
  * No third-party widget servers: nothing here can rate-limit or go dark.

Edit the CONFIG block below, run the script, commit.  Needs: pip install fonttools
"""
import datetime
import json
import math
import os
import random
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape as esc

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

# ----------------------------------------------------------------------------
# CONFIG  (edit me)
# ----------------------------------------------------------------------------
USER = "vivzz2216"
NAME_LINES = ("VIVEK", "PILLAI")
EMAIL = "pillaivivek200@gmail.com"
LINKEDIN = "https://www.linkedin.com/in/YOUR-HANDLE"  # <-- replace with your profile URL
OPEN_TO = "OPEN TO WORK  \u00b7  BACKEND & ML ENGINEERING"  # set to "" to hide the chip

KICKER = "// AI ENGINEER  \u00b7  FULL-STACK  \u00b7  AGENTIC SYSTEMS"
ROLES = [
    "autonomous agents, agentic workflows",
    "multimodal LLMs & diffusion pipelines",
    "full-stack platforms that scale",
]

PROJECTS = [
    dict(name="Qwen 2.1 Image Studio", repo="gwen-2.1-image-generation", cat="IMAGE GENERATION",
         desc="Diffusion image generation pipeline and creative workflow studio.",
         tags=["Python", "Diffusion", "PyTorch"], accent="cyan"),
    dict(name="Ethos AI Evaluator", repo="ethos-ai-evaluator", cat="AI EVALUATION",
         desc="Automated evaluation and benchmarking framework for intelligent systems.",
         tags=["TypeScript", "AI", "Testing"], accent="violet"),
    dict(name="CampusHub", repo="CampusHub", cat="FULL-STACK PLATFORM",
         desc="Scalable student & campus collaboration and resource management platform.",
         tags=["TypeScript", "React", "Node.js"], accent="pink"),
    dict(name="Face2Phase", repo="face2phase", cat="COMPUTER VISION",
         desc="Computer vision & biometric facial processing deep learning application.",
         tags=["Python", "OpenCV", "Deep Learning"], accent="amber"),
    dict(name="Pastebin Lite", repo="pastebin-lite", cat="DEVELOPER TOOL",
         desc="Fast, clean, lightweight paste and snippet sharing service.",
         tags=["TypeScript", "Web", "API"], accent="green"),
]

STACK = [  # (accent, scroll seconds, reverse?, items)
    ("cyan", 44, False, ["Python", "PyTorch", "Hugging Face", "Diffusion Models", "Ollama", "OpenCV",
                         "Agentic Workflows", "Multimodal LLMs", "Computer Vision"]),
    ("violet", 52, True, ["FastAPI", "TypeScript", "JavaScript", "React", "Next.js", "Node.js",
                          "Tailwind CSS", "Vite", "REST APIs"]),
    ("amber", 40, False, ["PostgreSQL", "Docker", "Linux", "Git", "GitHub", "VS Code"]),
]

# ----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = ROOT / "assets"
FONT_DIR = HERE / "fonts"

C = dict(bg0="#060812", bg1="#0b0f24", bg2="#150c32", panel="#0a0e1f", panel2="#0e1429",
         line="#1d2750", text="#eaf0ff", soft="#aab4de", muted="#8793c2",
         cyan="#22d3ee", violet="#a78bfa", pink="#f472b6", amber="#fbbf24",
         green="#34d399", blue="#60a5fa")


def fmt(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def n2(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s or "0"


# ----------------------------------------------------------------------------
# Fonts -> vector paths
# ----------------------------------------------------------------------------
class Font:
    def __init__(self, filename):
        self.font = TTFont(FONT_DIR / filename)
        self.gs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"]

    def _name(self, ch):
        name = self.cmap.get(ord(ch))
        if name is None:
            raise ValueError(f"glyph {ch!r} (U+{ord(ch):04X}) is missing from the font")
        return name

    def adv(self, ch, size):
        return self.hmtx[self._name(ch)][0] * size / self.upm

    def width(self, text, size, ls=0.0):
        if not text:
            return 0.0
        return sum(self.adv(c, size) for c in text) + ls * (len(text) - 1)

    def path(self, text, x, y, size, ls=0.0):
        pen = SVGPathPen(self.gs, ntos=fmt)
        s = size / self.upm
        cx = x
        for ch in text:
            name = self._name(ch)
            if ch != " ":
                self.gs[name].draw(TransformPen(pen, (s, 0, 0, -s, cx, y)))
            cx += self.hmtx[name][0] * s + ls
        return pen.getCommands()


DISP = Font("space-grotesk-latin-700-normal.woff")
SEMI = Font("space-grotesk-latin-500-normal.woff")
BODY = Font("space-grotesk-latin-400-normal.woff")
MONO = Font("jetbrains-mono-latin-500-normal.woff")
MONOB = Font("jetbrains-mono-latin-700-normal.woff")


def txt(font, text, x, y, size, fill, ls=0.0, anchor="start", opacity=None, extra=""):
    w = font.width(text, size, ls)
    if anchor == "end":
        x -= w
    elif anchor == "middle":
        x -= w / 2
    op = f' fill-opacity="{n2(opacity)}"' if opacity is not None else ""
    return f'<path d="{font.path(text, x, y, size, ls)}" fill="{fill}"{op}{extra}/>'


def wrap(font, text, size, maxw):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if font.width(t, size) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


# ----------------------------------------------------------------------------
# SVG / SMIL helpers
# ----------------------------------------------------------------------------
def svg_doc(w, h, title, desc, defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-labelledby="t d"><title id="t">{esc(title)}</title>'
            f'<desc id="d">{esc(desc)}</desc><defs>{defs}</defs>{body}</svg>\n')


def tl(attr, pts, total, calc="linear", extra="", splines=None):
    """<animate> from a timeline of (seconds, value) points, looping every `total` seconds."""
    pts = sorted(pts, key=lambda p: p[0])
    if pts[0][0] > 0:
        pts.insert(0, (0, pts[0][1]))
    if pts[-1][0] < total:
        pts.append((total, pts[-1][1]))
    ks, vs = [], []
    for t, v in pts:
        k = t / total
        if ks and k <= ks[-1]:
            k = ks[-1] + 1e-5
        ks.append(min(k, 1.0))
        vs.append(v)
    ks[0] = 0.0
    ks[-1] = 1.0
    kt = ";".join(f"{k:.5f}".rstrip("0").rstrip(".") or "0" for k in ks)
    vv = ";".join(n2(v) if isinstance(v, (int, float)) else str(v) for v in vs)
    sp = f' keySplines="{splines}"' if splines else ""
    return (f'<animate attributeName="{attr}" calcMode="{calc}" dur="{n2(total)}s" '
            f'repeatCount="indefinite" keyTimes="{kt}" values="{vv}"{sp}{extra}/>')


def rr_path(x, y, w, h, r):
    return (f"M{fmt(x + r)},{fmt(y)} H{fmt(x + w - r)} A{r},{r} 0 0 1 {fmt(x + w)},{fmt(y + r)} "
            f"V{fmt(y + h - r)} A{r},{r} 0 0 1 {fmt(x + w - r)},{fmt(y + h)} H{fmt(x + r)} "
            f"A{r},{r} 0 0 1 {fmt(x)},{fmt(y + h - r)} V{fmt(y + r)} A{r},{r} 0 0 1 {fmt(x + r)},{fmt(y)} Z")


def comet(d, color, dur, begin, dash="80 920", width=2.2, glow_id="glow"):
    """A bright segment that travels around a closed path."""
    anim = (f'<animate attributeName="stroke-dashoffset" values="0;-1000" dur="{dur}s" '
            f'begin="-{begin}s" repeatCount="indefinite"/>')
    common = (f'd="{d}" pathLength="1000" fill="none" stroke="{color}" stroke-linecap="round" '
              f'stroke-dasharray="{dash}"')
    return (f'<path {common} stroke-width="{width * 2.4}" opacity=".55" filter="url(#{glow_id})">{anim}</path>'
            f'<path {common} stroke-width="{width}">{anim}</path>')


GLOW = ('<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="3.2"/></filter>')


def arrow_ne(cx, cy, color, size=5.0, sw=1.8):
    s = size
    return (f'<path d="M{fmt(cx - s)},{fmt(cy + s)} L{fmt(cx + s)},{fmt(cy - s)} '
            f'M{fmt(cx - s * .55)},{fmt(cy - s)} H{fmt(cx + s)} V{fmt(cy + s * .55)}" '
            f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')


# ----------------------------------------------------------------------------
# Live data (GitHub REST API)
# ----------------------------------------------------------------------------
LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "HTML": "#e34c26",
    "CSS": "#8b6cf0", "Jupyter Notebook": "#DA5B0B", "Shell": "#89e051", "Dockerfile": "#4b6c84",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#8a8a8a", "Go": "#00ADD8", "Rust": "#dea584",
    "SCSS": "#c6538c", "PLpgSQL": "#336790", "Vue": "#41b883", "Other": "#5b6591",
}
FALLBACK_COLORS = [C["cyan"], C["violet"], C["pink"], C["amber"], C["green"], C["blue"]]


def gh(path, token=None):
    url = path if path.startswith("http") else "https://api.github.com" + path
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "profile-readme-build"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def refresh_data():
    token = os.environ.get("GITHUB_TOKEN")
    user = gh(f"/users/{USER}", token)
    repos, page = [], 1
    while True:
        chunk = gh(f"/users/{USER}/repos?per_page=100&page={page}&type=owner&sort=pushed", token)
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = {}
    for r in own[:40]:
        try:
            for k, v in gh(r["languages_url"], token).items():
                langs[k] = langs.get(k, 0) + v
        except Exception as e:  # one bad repo should not sink the run
            print("  languages skipped for", r["name"], "-", e)
    total = sum(langs.values()) or 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    top = [[k, round(100 * v / total, 1)] for k, v in ranked[:5]]
    rest = round(100 - sum(p for _, p in top), 1)
    if rest > 0.4 and len(ranked) > 5:
        top.append(["Other", rest])
    commits = None
    try:
        commits = gh(f"/search/commits?q=author:{USER}&per_page=1", token)["total_count"]
    except Exception as e:
        print("  commit count skipped -", e)
    data = dict(
        synced=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        repos=user["public_repos"],
        stars=sum(r["stargazers_count"] for r in own),
        forks=sum(r["forks_count"] for r in own),
        followers=user["followers"],
        commits=commits,
        languages=top,
        recent=[dict(name=r["name"], pushed=r["pushed_at"]) for r in own[:3]],
        repo_meta={r["name"].lower(): dict(stars=r["stargazers_count"], language=r["language"],
                                           pushed=r["pushed_at"]) for r in repos},
    )
    (ASSETS / "data.json").write_text(json.dumps(data, indent=2))
    print("  live data refreshed:", data["synced"])


def load_data():
    p = ASSETS / "data.json"
    return json.loads(p.read_text()) if p.exists() else None


def time_ago(iso):
    t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    s = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()
    if s < 3600 * 48:
        return f"{max(1, int(s // 3600))}h ago"
    if s < 86400 * 60:
        return f"{int(s // 86400)}d ago"
    return f"{int(s // (86400 * 30))}mo ago"


# ----------------------------------------------------------------------------
# 1. BANNER
# ----------------------------------------------------------------------------
def banner():
    W, H = 1000, 384
    rnd = random.Random(11)

    layers = [(612, 3), (698, 5), (784, 6), (868, 5), (948, 3)]
    nodes = []
    for x, cnt in layers:
        nodes.append([(x + rnd.uniform(-8, 8), 58 + (H - 118) * (i + .5) / cnt + rnd.uniform(-10, 10))
                      for i in range(cnt)])
    edges = []
    for li in range(len(nodes) - 1):
        A, B = nodes[li], nodes[li + 1]
        seen = set()
        for ai, (ax, ay) in enumerate(A):
            for bi in sorted(range(len(B)), key=lambda b: abs(B[b][1] - ay))[:2]:
                seen.add((ai, bi))
        for bi, (bx, by) in enumerate(B):
            if not any(b == bi for _, b in seen):
                seen.add((min(range(len(A)), key=lambda a: abs(A[a][1] - by)), bi))
        for ai, bi in sorted(seen):
            edges.append((*A[ai], *B[bi]))
    layer_cols = [C["cyan"], C["blue"], C["violet"], "#c084fc", C["pink"]]

    net = ['<path d="' + " ".join(f"M{fmt(a)},{fmt(b)} L{fmt(c)},{fmt(d)}" for a, b, c, d in edges) +
           '" stroke="#7c8cff" stroke-opacity=".24" stroke-width="1" fill="none"/>']
    for ex in rnd.sample(edges, 17):
        ax, ay, bx, by = ex
        col = rnd.choice([C["cyan"], C["pink"], C["violet"], "#ffffff"])
        dur = round(rnd.uniform(2.4, 4.4), 1)
        beg = round(rnd.uniform(0, dur), 2)
        net.append(
            f'<g><circle cx="{fmt(ax)}" cy="{fmt(ay)}" r="7" fill="{col}" fill-opacity=".16"/>'
            f'<circle cx="{fmt(ax)}" cy="{fmt(ay)}" r="2.3" fill="{col}"/>'
            f'<animateMotion dur="{dur}s" begin="-{beg}s" repeatCount="indefinite" '
            f'path="M0,0 L{fmt(bx - ax)},{fmt(by - ay)}"/>'
            f'<animate attributeName="opacity" dur="{dur}s" begin="-{beg}s" repeatCount="indefinite" '
            f'values="0;1;1;0" keyTimes="0;.15;.85;1"/></g>')
    for li, layer in enumerate(nodes):
        for (x, y) in layer:
            col = layer_cols[li]
            net.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="5.2" fill="{C["bg1"]}" stroke="{col}" stroke-width="1.6"/>'
                       f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="1.9" fill="{col}"/>')
    for (x, y) in rnd.sample([p for layer in nodes for p in layer], 9):
        beg = round(rnd.uniform(0, 3.4), 2)
        net.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="5" fill="none" stroke="{C["cyan"]}" stroke-width="1.2">'
                   f'<animate attributeName="r" values="5;17" dur="3.4s" begin="-{beg}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="stroke-opacity" values=".7;0" dur="3.4s" begin="-{beg}s" repeatCount="indefinite"/></circle>')

    # text geometry
    x0, size = 52, 104
    base1, base2 = 168, 260
    ls = 1.5
    name_d = DISP.path(NAME_LINES[0], x0, base1, size, ls) + " " + DISP.path(NAME_LINES[1], x0, base2, size, ls)

    # typewriter roles
    role_size, role_base = 20, 308
    prompt_w = MONO.width("> ", role_size)
    T = 4.6 * len(ROLES)
    roles = [txt(MONOB, ">", x0, role_base, role_size, C["cyan"])]
    for i, phrase in enumerate(ROLES):
        s = i * 4.6
        cum = [MONO.width(phrase[:k], role_size) for k in range(len(phrase) + 1)]
        t0 = s + 0.3
        dt = 0.05
        wev = [(t0 + k * dt, cum[k]) for k in range(1, len(phrase) + 1)]
        cev = [(t0 + k * dt, x0 + prompt_w + cum[k]) for k in range(1, len(phrase) + 1)]
        full = cum[-1]
        cid = f"role{i}"
        op_pts = ([(0, 1), (s + 4.0, 1), (s + 4.5, 0), (T, 0)] if i == 0 else
                  [(0, 0), (s, 0), (s + .15, 1), (s + 4.0, 1), (s + 4.5, 0), (T, 0)])
        roles.append(
            f'<clipPath id="{cid}"><rect x="{fmt(x0 + prompt_w - 2)}" y="{role_base - 22}" height="30" width="{fmt(full + 6)}">'
            f'{tl("width", [(0, 0)] + [(t, w + 3) for t, w in wev] + [(T, full + 6)], T, "discrete")}</rect></clipPath>'
            f'<g>{tl("opacity", op_pts, T)}'
            f'<g clip-path="url(#{cid})">{txt(MONO, phrase, x0 + prompt_w, role_base, role_size, "#dfe6ff")}</g>'
            f'<rect y="{role_base - 17}" width="11" height="22" fill="{C["cyan"]}" x="{fmt(x0 + prompt_w + full)}">'
            f'{tl("x", [(0, x0 + prompt_w)] + cev + [(T, x0 + prompt_w + full)], T, "discrete")}'
            f'<animate attributeName="fill-opacity" values="1;.15" dur="1s" calcMode="discrete" repeatCount="indefinite"/>'
            f'</rect></g>')

    chip = ""
    if OPEN_TO:
        cw = MONO.width(OPEN_TO, 12, 1.5) + 46
        chip = (f'<g transform="translate({x0},328)">'
                f'<rect width="{fmt(cw)}" height="30" rx="15" fill="{C["green"]}" fill-opacity=".08" '
                f'stroke="{C["green"]}" stroke-opacity=".45"/>'
                f'<circle cx="17" cy="15" r="4" fill="{C["green"]}"/>'
                f'<circle cx="17" cy="15" r="4" fill="none" stroke="{C["green"]}">'
                f'<animate attributeName="r" values="4;12" dur="2s" repeatCount="indefinite"/>'
                f'<animate attributeName="stroke-opacity" values=".8;0" dur="2s" repeatCount="indefinite"/></circle>'
                f'{txt(MONO, OPEN_TO, 32, 19.5, 12, "#a7f3d0", 1.5)}</g>')

    defs = f'''
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C['bg0']}"/><stop offset=".55" stop-color="{C['bg1']}"/><stop offset="1" stop-color="{C['bg2']}"/></linearGradient>
<radialGradient id="aC"><stop offset="0" stop-color="{C['cyan']}" stop-opacity=".32"/><stop offset="1" stop-color="{C['cyan']}" stop-opacity="0"/></radialGradient>
<radialGradient id="aV"><stop offset="0" stop-color="{C['violet']}" stop-opacity=".34"/><stop offset="1" stop-color="{C['violet']}" stop-opacity="0"/></radialGradient>
<radialGradient id="aP"><stop offset="0" stop-color="{C['pink']}" stop-opacity=".26"/><stop offset="1" stop-color="{C['pink']}" stop-opacity="0"/></radialGradient>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1" fill="#9fb0ff" fill-opacity=".14"/></pattern>
<linearGradient id="netFade" gradientUnits="userSpaceOnUse" x1="540" y1="0" x2="690" y2="0"><stop offset="0" stop-color="#000"/><stop offset="1" stop-color="#fff"/></linearGradient>
<mask id="netMask"><rect width="{W}" height="{H}" fill="url(#netFade)"/></mask>
<linearGradient id="nameG" gradientUnits="userSpaceOnUse" x1="{x0}" y1="0" x2="{x0 + 360}" y2="0" spreadMethod="repeat">
  <stop offset="0" stop-color="#eafcff"/><stop offset=".25" stop-color="{C['cyan']}"/><stop offset=".5" stop-color="{C['violet']}"/><stop offset=".75" stop-color="{C['pink']}"/><stop offset="1" stop-color="#eafcff"/>
  <animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="360 0" dur="7s" repeatCount="indefinite"/>
</linearGradient>
<linearGradient id="scan" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C['cyan']}" stop-opacity="0"/><stop offset=".5" stop-color="{C['cyan']}" stop-opacity=".35"/><stop offset="1" stop-color="{C['cyan']}" stop-opacity="0"/></linearGradient>
<filter id="blurBig" x="-20%" y="-30%" width="140%" height="160%"><feGaussianBlur stdDeviation="16"/></filter>
<clipPath id="frame"><rect width="{W}" height="{H}" rx="22"/></clipPath>
<path id="nameP" d="{name_d}"/>'''

    corners = "".join(
        f'<path d="{d}" fill="none" stroke="{C["cyan"]}" stroke-opacity=".55" stroke-width="1.6" stroke-linecap="round"/>'
        for d in ("M20,44 V24 Q20,20 24,20 H44", f"M{W - 44},20 H{W - 24} Q{W - 20},20 {W - 20},24 V44",
                  f"M20,{H - 44} V{H - 24} Q20,{H - 20} 24,{H - 20} H44",
                  f"M{W - 44},{H - 20} H{W - 24} Q{W - 20},{H - 20} {W - 20},{H - 24} V{H - 44}"))

    body = f'''
<g clip-path="url(#frame)">
  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" fill="url(#dots)"/>
  <circle cx="820" cy="70" r="300" fill="url(#aC)"><animate attributeName="cx" values="770;880;770" dur="16s" repeatCount="indefinite" calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1"/></circle>
  <circle cx="690" cy="340" r="320" fill="url(#aV)"><animate attributeName="cy" values="300;380;300" dur="19s" repeatCount="indefinite" calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1"/></circle>
  <circle cx="90" cy="380" r="280" fill="url(#aP)"><animate attributeName="cx" values="60;190;60" dur="22s" repeatCount="indefinite" calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1"/></circle>
  <g mask="url(#netMask)">{''.join(net)}</g>
  <rect x="0" y="-10" width="{W}" height="2" fill="url(#scan)"><animate attributeName="y" values="-10;{H + 10}" dur="8s" repeatCount="indefinite"/></rect>
  {txt(MONO, KICKER, x0, 70, 13.5, C['cyan'], 2.2)}
  <use href="#nameP" fill="#8b5cf6" fill-opacity=".55" filter="url(#blurBig)"/>
  <use href="#nameP" fill="url(#nameG)"/>
  {''.join(roles)}
  {chip}
  {corners}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="{C['line']}"/>'''
    return svg_doc(W, H, "Vivek Pillai - AI Engineer, Full-Stack Developer, Agentic Systems",
                   "Animated banner: a neural network with pulses of light, the name Vivek Pillai, and rotating role headlines.",
                   defs, body)


# ----------------------------------------------------------------------------
# 2. TERMINAL
# ----------------------------------------------------------------------------
def terminal():
    W, H = 1000, 342
    total = 22.0
    size, pitch, y0, x0 = 17, 28, 86, 34
    K = lambda k, v: [(k, C["cyan"]), (v, C["text"])]
    lines = [
        ("cmd", [("$ ", C["green"]), ("whoami", C["text"])]),
        ("out", [("Vivek Pillai \u2014 AI engineer \u00b7 full-stack developer", C["soft"])]),
        ("cmd", [("$ ", C["green"]), ("cat focus.yml", C["text"])]),
        ("out", K("building:  ", "autonomous agents \u00b7 multimodal LLM workflows")),
        ("out", K("stack:     ", "Python \u00b7 PyTorch \u00b7 FastAPI \u00b7 TypeScript \u00b7 React")),
        ("out", K("ships:     ", "diffusion studios \u00b7 eval frameworks \u00b7 campus platforms")),
        ("cmd", [("$ ", C["green"]), ("./open-to --roles", C["text"])]),
        ("out", [("Backend Engineer  \u00b7  AI/ML Engineer", C["green"])]),
        ("cmd", [("$ ", C["green"])]),
    ]
    t = 0.7
    clips, rows, cursor_ev = [], [], []
    for i, (kind, segs) in enumerate(lines):
        base = y0 + i * pitch
        text = "".join(s for s, _ in segs)
        step = 0.06 if kind == "cmd" else 0.013
        cum = [MONO.width(text[:k], size) for k in range(len(text) + 1)]
        full = cum[-1]
        ev = []
        for k in range(1, len(text) + 1):
            ev.append((t + k * step, cum[k]))
            cursor_ev.append((t + k * step, x0 + cum[k], base))
        if not ev:  # empty line safety
            ev = [(t, 0)]
        t = ev[-1][0] + (0.55 if kind == "out" else 0.4)
        cid = f"tl{i}"
        clips.append(f'<clipPath id="{cid}"><rect x="{x0 - 2}" y="{base - 21}" height="30" width="{fmt(full + 8)}">'
                     f'{tl("width", [(0, 0)] + [(a, b + 4) for a, b in ev] + [(total, full + 8)], total, "discrete")}</rect></clipPath>')
        x = x0
        paths = []
        for s, col in segs:
            paths.append(txt(MONO, s, x, base, size, col))
            x += MONO.width(s, size)
        rows.append(f'<g clip-path="url(#{cid})">{"".join(paths)}</g>')
    last_x = x0 + MONO.width("$ ", size)
    last_base = y0 + (len(lines) - 1) * pitch
    cursor = (f'<rect width="10" height="21" x="{fmt(last_x)}" y="{last_base - 16}" fill="{C["cyan"]}">'
              + tl("x", [(0, x0)] + [(a, b) for a, b, _ in cursor_ev] + [(total, last_x)], total, "discrete")
              + tl("y", [(0, y0 - 16)] + [(a, c - 16) for a, _, c in cursor_ev] + [(total, last_base - 16)], total, "discrete")
              + '<animate attributeName="fill-opacity" values="1;.1" dur="1.05s" calcMode="discrete" repeatCount="indefinite"/></rect>')

    defs = f'''
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" fill-opacity=".028"/></pattern>
<radialGradient id="tg" cx=".9" cy="0" r=".9"><stop offset="0" stop-color="{C['violet']}" stop-opacity=".16"/><stop offset="1" stop-color="{C['violet']}" stop-opacity="0"/></radialGradient>
<clipPath id="frame"><rect width="{W}" height="{H}" rx="16"/></clipPath>{''.join(clips)}'''
    title = txt(MONO, "vivek@lab \u2014 ~/profile", W / 2, 27, 13, C["muted"], 0.5, "middle")
    body = f'''
<g clip-path="url(#frame)">
  <rect width="{W}" height="{H}" fill="{C['panel']}"/>
  <rect width="{W}" height="{H}" fill="url(#tg)"/>
  <rect width="{W}" height="46" fill="{C['panel2']}"/>
  <path d="M0,46 H{W}" stroke="{C['line']}"/>
  <circle cx="28" cy="23" r="6.5" fill="#ff5f57"/><circle cx="50" cy="23" r="6.5" fill="#febc2e"/><circle cx="72" cy="23" r="6.5" fill="#28c840"/>
  {title}
  <g>{tl("opacity", [(0, 1), (total - 3.2, 1), (total - 2.4, 0), (total, 0)], total)}
    {''.join(rows)}{cursor}
  </g>
  <rect width="{W}" height="{H}" fill="url(#scan)"/>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="15.5" fill="none" stroke="{C['line']}"/>'''
    return svg_doc(W, H, "Terminal: about Vivek Pillai",
                   "A terminal window that types out: whoami, focus.yml with building, stack and ships, and open-to roles Backend Engineer and AI/ML Engineer.",
                   defs, body)


# ----------------------------------------------------------------------------
# 3. STACK MARQUEE
# ----------------------------------------------------------------------------
def stack():
    W = 1000
    pill_h, gap, pad, row_gap = 44, 14, 20, 16
    H = pad * 2 + len(STACK) * pill_h + (len(STACK) - 1) * row_gap
    rows = []
    for r, (accent, dur, reverse, items) in enumerate(STACK):
        col = C[accent]
        y = pad + r * (pill_h + row_gap)
        seq = list(items)
        widths = lambda s: sum(SEMI.width(i, 17) + 56 + gap for i in s)
        while widths(seq) < W + 240:
            seq += items
        period = widths(seq)

        def one_copy(offset):
            out, x = [], offset
            for item in seq:
                tw = SEMI.width(item, 17)
                w = tw + 56
                out.append(f'<rect x="{fmt(x)}" y="{y}" width="{fmt(w)}" height="{pill_h}" rx="22" fill="{col}" '
                           f'fill-opacity=".08" stroke="{col}" stroke-opacity=".38"/>'
                           f'<circle cx="{fmt(x + 22)}" cy="{y + pill_h / 2}" r="4.5" fill="{col}"/>'
                           + txt(SEMI, item, x + 36, y + 28, 17, C["text"]))
                x += w + gap
            return "".join(out)

        frm, to = ("-%s 0" % fmt(period), "0 0") if reverse else ("0 0", "-%s 0" % fmt(period))
        rows.append(f'<g><animateTransform attributeName="transform" type="translate" from="{frm}" to="{to}" '
                    f'dur="{dur}s" repeatCount="indefinite"/>{one_copy(0)}{one_copy(period)}</g>')
    defs = f'''
<linearGradient id="fd" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000"/><stop offset=".08" stop-color="#fff"/><stop offset=".92" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
<mask id="mk"><rect width="{W}" height="{H}" fill="url(#fd)"/></mask>'''
    body = f'''
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="{C['panel']}" stroke="{C['line']}"/>
<g mask="url(#mk)">{''.join(rows)}</g>'''
    return svg_doc(W, H, "Tech stack",
                   "Three scrolling rows of technologies: AI and ML (Python, PyTorch, Hugging Face, Diffusion, Ollama, OpenCV), "
                   "web and backend (FastAPI, TypeScript, React, Next.js, Node.js), and data and tooling (PostgreSQL, Docker, Linux, Git).",
                   defs, body)


# ----------------------------------------------------------------------------
# 4. SECTION HEADERS
# ----------------------------------------------------------------------------
def section(idx, title, sub):
    W, H, PH = 1000, 70, 58
    tw = DISP.width(title, 26, 1.2)
    sw = MONO.width(sub, 12, 0.6)
    lx1, lx2 = 62 + tw + 24, 976 - sw - 24
    L = lx2 - lx1
    defs = f'''
<linearGradient id="ln" gradientUnits="userSpaceOnUse" x1="{fmt(lx1)}" y1="0" x2="{fmt(lx2)}" y2="0"><stop offset="0" stop-color="{C['cyan']}" stop-opacity=".7"/><stop offset="1" stop-color="{C['violet']}" stop-opacity=".1"/></linearGradient>
<linearGradient id="ab" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C['cyan']}"/><stop offset="1" stop-color="{C['violet']}"/></linearGradient>
<clipPath id="frame"><rect width="{W}" height="{PH}" rx="14"/></clipPath>'''
    body = f'''
<g clip-path="url(#frame)">
  <rect width="{W}" height="{PH}" fill="{C['panel']}"/>
  <rect width="5" height="{PH}" fill="url(#ab)"/>
  {txt(MONOB, idx, 28, 35, 14, C['cyan'], 1)}
  {txt(DISP, title, 62, 39, 26, C['text'], 1.2)}
  <line x1="{fmt(lx1)}" y1="29" x2="{fmt(lx2)}" y2="29" stroke="url(#ln)" stroke-width="1.5"/>
  <line x1="{fmt(lx1)}" y1="29" x2="{fmt(lx2)}" y2="29" stroke="{C['cyan']}" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="34 {fmt(L + 40)}">
    <animate attributeName="stroke-dashoffset" values="34;{fmt(-L)}" dur="3.6s" repeatCount="indefinite"/></line>
  {txt(MONO, sub, 976, 34, 12, C['muted'], 0.6, 'end')}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{PH - 1}" rx="13.5" fill="none" stroke="{C['line']}"/>'''
    return svg_doc(W, H, f"{idx} {title}", sub, defs, body)


# ----------------------------------------------------------------------------
# 5. PROJECT CARDS
# ----------------------------------------------------------------------------
def card(i, p, data, w=494, h=220):
    col = C[p["accent"]]
    pad = 26
    meta = (data or {}).get("repo_meta", {}).get(p["repo"].lower())
    d = rr_path(1, 1, w - 2, h - 2, 17)
    idx = f"{i + 1:02d}"
    lines = wrap(BODY, p["desc"], 15.5, w - 2 * pad)[:3]
    tags, x = [], pad
    ty = h - 52
    for tg in p["tags"]:
        tw = MONO.width(tg, 12)
        tags.append(f'<rect x="{fmt(x)}" y="{ty}" width="{fmt(tw + 22)}" height="26" rx="13" fill="{col}" '
                    f'fill-opacity=".1" stroke="{col}" stroke-opacity=".32"/>'
                    + txt(MONO, tg, x + 11, ty + 17.5, 12, col))
        x += tw + 22 + 8
    live = ""
    if meta:
        label = f"updated {time_ago(meta['pushed'])}" if meta.get("pushed") else ""
        stars = meta.get("stars") or 0
        if stars:
            label = f"{stars}  \u00b7  {label}" if label else str(stars)
        if label:
            live = txt(MONO, label, w - pad, h - 34.5, 12, C["muted"], 0, "end")
        if stars:  # the star glyph is not in the font subset, so draw it as a vector
            sx = w - pad - MONO.width(label, 12) - 16
            live += (f'<path transform="translate({fmt(sx)},{h - 44.5}) scale(.66)" fill="{C["amber"]}" '
                     f'd="M8,0 L10.4,5.2 16,5.9 11.8,9.7 12.9,15.3 8,12.5 3.1,15.3 4.2,9.7 0,5.9 5.6,5.2Z"/>')
    desc = "".join(txt(BODY, ln, pad, 128 + k * 23, 15.5, C["soft"]) for k, ln in enumerate(lines))
    defs = f'''
<radialGradient id="gl" cx="1" cy="0" r="1"><stop offset="0" stop-color="{col}" stop-opacity=".24"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></radialGradient>
<linearGradient id="pf" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d1328"/><stop offset="1" stop-color="#090c1b"/></linearGradient>
<clipPath id="frame"><path d="{d}"/></clipPath>{GLOW}'''
    body = f'''
<g clip-path="url(#frame)">
  <path d="{d}" fill="url(#pf)"/>
  <rect width="{w}" height="{h}" fill="url(#gl)"/>
</g>
<path d="{d}" fill="none" stroke="{C['line']}" stroke-width="1.4"/>
{comet(d, col, 7.5, i * 1.9)}
{txt(MONOB, idx, pad, 40, 13, col, 1)}
{txt(MONO, p['cat'], pad + 34, 40, 11.5, C['muted'], 2)}
<circle cx="{w - 42}" cy="38" r="17" fill="{col}" fill-opacity=".08" stroke="{col}" stroke-opacity=".4"/>
{arrow_ne(w - 42, 38, col)}
{txt(DISP, p['name'], pad, 94, 29, C['text'])}
{desc}
{''.join(tags)}
{live}'''
    return svg_doc(w, h + 10, p["name"], p["desc"] + " Tags: " + ", ".join(p["tags"]), defs, body)


def card_cta(w=494, h=220):
    col = C["blue"]
    d = rr_path(1, 1, w - 2, h - 2, 17)
    chev = "".join(
        f'<path d="M{w - 150 + k * 22},{h / 2 - 16} l14,16 l-14,16" fill="none" stroke="{col}" stroke-width="3" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity=".25">'
        f'<animate attributeName="opacity" values=".15;1;.15" dur="1.8s" begin="-{1.8 - k * .3}s" repeatCount="indefinite"/></path>'
        for k in range(3))
    defs = f'''
<linearGradient id="pf" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d1530"/><stop offset="1" stop-color="#150f33"/></linearGradient>
<clipPath id="frame"><path d="{d}"/></clipPath>{GLOW}'''
    body = f'''
<g clip-path="url(#frame)"><path d="{d}" fill="url(#pf)"/></g>
<path d="{d}" fill="none" stroke="{col}" stroke-opacity=".4" stroke-width="1.4" stroke-dasharray="6 7"/>
{comet(d, col, 9, 3)}
{txt(MONOB, "+", 26, 40, 13, col, 1)}
{txt(MONO, "AND MORE", 26 + 20, 40, 11.5, C['muted'], 2)}
{txt(DISP, "All repositories", 26, 94, 29, C['text'])}
{txt(BODY, "Experiments, prototypes and works in", 26, 128, 15.5, C['soft'])}
{txt(BODY, "progress \u2014 the full list lives on GitHub.", 26, 151, 15.5, C['soft'])}
{txt(MONO, f"github.com/{USER}", 26, h - 34, 13, col)}
{chev}'''
    return svg_doc(w, h + 10, "All repositories", f"Link to every repository on github.com/{USER}", defs, body)


# ----------------------------------------------------------------------------
# 6. STATS
# ----------------------------------------------------------------------------
def stats(data):
    W, H = 1000, 306
    live = bool(data)
    tiles = [
        ("PUBLIC REPOS", data["repos"] if live else None, C["cyan"]),
        ("STARS EARNED", data["stars"] if live else None, C["amber"]),
        ("FOLLOWERS", data["followers"] if live else None, C["pink"]),
    ]
    if live and data.get("commits") is not None:
        tiles.append(("PUBLIC COMMITS", data["commits"], C["violet"]))
    else:
        tiles.append(("FORKS", data["forks"] if live else None, C["violet"]))
    tw, th, gx = 232, 104, 16
    body, defs = [], [f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="16"/></clipPath>']
    for k, (label, val, col) in enumerate(tiles):
        x = 28 + (k % 2) * (tw + gx)
        y = 28 + (k // 2) * (th + gx)
        delay = 0.12 * k / 1.3
        shown = f"{val:,}" if val is not None else "\u2014"
        body.append(
            f'<g transform="translate({x},{y})">'
            f'<animateTransform attributeName="transform" type="translate" additive="sum" calcMode="spline" '
            f'keyTimes="0;{n2(delay + 0.0001)};1" keySplines="0 0 1 1;.2 .8 .2 1" values="0 14;0 14;0 0" dur="1.3s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{n2(delay + 0.0001)};1" dur="1.3s" fill="freeze"/>'
            f'<rect width="{tw}" height="{th}" rx="13" fill="{C["panel2"]}" stroke="{C["line"]}"/>'
            f'<rect x="20" y="22" width="28" height="3" rx="1.5" fill="{col}"/>'
            f'{txt(DISP, shown, 20, 74, 44, C["text"])}'
            f'{txt(MONO, label, 20, 96, 11.5, C["muted"], 2)}'
            f'</g>')
    x0, bw = 560, 412
    body.append(txt(MONO, "LANGUAGES  \u00b7  BY CODE VOLUME", x0, 44, 12, C["muted"], 2))
    if live and data.get("languages"):
        segs, x = [], x0
        legend = []
        for k, (name, pct) in enumerate(data["languages"]):
            colr = LANG_COLORS.get(name, FALLBACK_COLORS[k % len(FALLBACK_COLORS)])
            sw = bw * pct / 100
            segs.append(f'<rect x="{fmt(x)}" y="58" width="{fmt(max(sw - 2, 1))}" height="18" fill="{colr}"/>')
            x += sw
            cx = x0 + (k % 2) * 212
            cy = 114 + (k // 2) * 30
            legend.append(f'<circle cx="{cx + 5}" cy="{cy - 5}" r="5" fill="{colr}"/>'
                          + txt(SEMI, name, cx + 18, cy, 15, C["text"])
                          + txt(MONO, f"{pct:g}%", cx + 190, cy, 12.5, C["muted"], 0, "end"))
        defs.append(f'<clipPath id="barShape"><rect x="{x0}" y="58" width="{bw}" height="18" rx="9"/></clipPath>'
                    f'<clipPath id="barReveal"><rect x="{x0}" y="54" height="26" width="{bw}">'
                    f'<animate attributeName="width" values="0;{bw}" keyTimes="0;1" calcMode="spline" keySplines=".2 .8 .2 1" dur="1.6s" fill="freeze"/></rect></clipPath>')
        body.append(f'<rect x="{x0}" y="58" width="{bw}" height="18" rx="9" fill="{C["panel2"]}"/>'
                    f'<g clip-path="url(#barShape)"><g clip-path="url(#barReveal)">{"".join(segs)}</g></g>')
        body.append("".join(legend))
    else:
        defs.append(f'<linearGradient id="sh" gradientUnits="userSpaceOnUse" x1="{x0}" y1="0" x2="{x0 + 160}" y2="0" spreadMethod="repeat">'
                    f'<stop offset="0" stop-color="{C["panel2"]}"/><stop offset=".5" stop-color="{C["cyan"]}" stop-opacity=".55"/><stop offset="1" stop-color="{C["panel2"]}"/>'
                    f'<animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="160 0" dur="1.8s" repeatCount="indefinite"/></linearGradient>')
        body.append(f'<rect x="{x0}" y="58" width="{bw}" height="18" rx="9" fill="url(#sh)"/>')
        body.append(txt(BODY, "Syncing with the GitHub API\u2026", x0, 118, 15, C["soft"]))
        body.append(txt(MONO, "first run happens automatically after you push", x0, 142, 12, C["muted"], 0.3))
    if live and data.get("recent"):
        body.append(txt(MONO, "RECENTLY PUSHED", x0, 214, 12, C["muted"], 2))
        for k, r in enumerate(data["recent"][:3]):
            y = 240 + k * 22
            body.append(f'<circle cx="{x0 + 4}" cy="{y - 4}" r="3" fill="{C["green"]}"/>'
                        + txt(MONO, r["name"], x0 + 18, y, 13, C["text"])
                        + txt(MONO, time_ago(r["pushed"]), x0 + bw, y, 12, C["muted"], 0, "end"))
    stamp = f"synced {data['synced']} UTC \u00b7 github api" if live else "awaiting first sync"
    body.append(txt(MONO, stamp, 28, H - 16, 11, C["muted"], 0.6, opacity=.8))
    out = f'''
<g clip-path="url(#frame)"><rect width="{W}" height="{H}" fill="{C['panel']}"/>
<path d="M{x0 - 24},24 V{H - 24}" stroke="{C['line']}"/>{''.join(body)}</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="15.5" fill="none" stroke="{C['line']}"/>'''
    return svg_doc(W, H, "GitHub numbers",
                   "Public repositories, stars, followers and commits, with a language breakdown, generated from the GitHub API.",
                   "".join(defs), out)


# ----------------------------------------------------------------------------
# 7. BUTTONS + FOOTER
# ----------------------------------------------------------------------------
def button(label, sub, col):
    w, h = 214, 58
    d = rr_path(1, 1, w - 2, h - 2, 15)
    defs = f'<clipPath id="frame"><path d="{d}"/></clipPath>{GLOW}'
    body = f'''
<g clip-path="url(#frame)"><path d="{d}" fill="{C['panel']}"/><rect width="{w}" height="{h}" fill="{col}" fill-opacity=".05"/></g>
<path d="{d}" fill="none" stroke="{C['line']}" stroke-width="1.3"/>
{comet(d, col, 5.5, sum(map(ord, label)) % 5, dash="120 880", width=2)}
{txt(DISP, label, 22, 27, 17, C['text'], 1.4)}
{txt(MONO, sub, 22, 45, 12, col)}
<circle cx="{w - 32}" cy="{h / 2}" r="14" fill="{col}" fill-opacity=".1" stroke="{col}" stroke-opacity=".4"/>
{arrow_ne(w - 32, h / 2, col, 4.2, 1.7)}'''
    return svg_doc(w, h, label, sub, defs, body)


def footer():
    W, H = 1000, 168

    def wave(base, amp, period, phase, col, op, dur, rev=False):
        pts = " ".join(f"L{x},{fmt(base + amp * math.sin(2 * math.pi * x / period + phase))}"
                       for x in range(0, W + period + 11, 10))
        d = f"M0,{H} {pts} L{W + period + 10},{H} Z"
        frm, to = ("-%d 0" % period, "0 0") if rev else ("0 0", "-%d 0" % period)
        return (f'<path d="{d}" fill="{col}" fill-opacity="{op}"><animateTransform attributeName="transform" type="translate" '
                f'from="{frm}" to="{to}" dur="{dur}s" repeatCount="indefinite"/></path>')

    defs = f'''<linearGradient id="fg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C['cyan']}"/><stop offset=".5" stop-color="{C['violet']}"/><stop offset="1" stop-color="{C['pink']}"/></linearGradient>
<clipPath id="frame"><rect width="{W}" height="{H}" rx="18"/></clipPath>'''
    sub = "this profile renders itself  \u00b7  scripts/build.py  \u00b7  refreshed daily by GitHub Actions"
    body = f'''
<g clip-path="url(#frame)">
  <rect width="{W}" height="{H}" fill="{C['panel']}"/>
  {wave(128, 9, 500, 0, 'url(#fg)', .22, 14)}
  {wave(138, 8, 400, 1.7, 'url(#fg)', .3, 10, True)}
  {wave(148, 6, 250, 3.1, 'url(#fg)', .45, 7)}
  {txt(DISP, "Thanks for stopping by.", W / 2, 60, 24, C['text'], 0.4, 'middle')}
  {txt(MONO, sub, W / 2, 88, 12, C['muted'], 0.5, 'middle')}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="17.5" fill="none" stroke="{C['line']}"/>'''
    return svg_doc(W, H, "Footer", "Thanks for stopping by. This profile renders itself and is refreshed daily by GitHub Actions.", defs, body)


# ----------------------------------------------------------------------------
def write(name, content):
    (ASSETS / name).write_text(content, encoding="utf-8")
    print(f"  {name:<22}{len(content) / 1024:6.1f} KB")


def main():
    ASSETS.mkdir(exist_ok=True)
    if "--live" in sys.argv:
        try:
            refresh_data()
        except Exception as e:  # keep the previous data.json if the API hiccups
            print("  live refresh failed, keeping previous data:", e)
    data = load_data()
    print("building assets...")
    write("banner.svg", banner())
    write("terminal.svg", terminal())
    write("stack.svg", stack())
    write("sec-stack.svg", section("01", "STACK", "the tools I reach for"))
    write("sec-work.svg", section("02", "SELECTED WORK", "things I have built"))
    write("sec-numbers.svg", section("03", "BY THE NUMBERS", "pulled live from the GitHub API"))
    write("sec-activity.svg", section("04", "CONTRIBUTIONS", "the snake is hungry"))
    for i, p in enumerate(PROJECTS):
        write(f"card-{i + 1}.svg", card(i, p, data))
    write(f"card-{len(PROJECTS) + 1}.svg", card_cta())
    write("stats.svg", stats(data))
    write("btn-github.svg", button("GITHUB", f"@{USER}", C["cyan"]))
    write("btn-linkedin.svg", button("LINKEDIN", "let's connect", C["blue"]))
    write("btn-email.svg", button("EMAIL", "say hello", C["pink"]))
    write("footer.svg", footer())


if __name__ == "__main__":
    main()
