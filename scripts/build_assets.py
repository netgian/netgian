"""Build the animated SVG assets used by the profile README.

    python scripts/build_assets.py

Text is converted to vector paths so the images render the same everywhere
(GitHub serves README images through a sandboxed proxy where web fonts are
unreliable). Motion is plain CSS inside each SVG and stops under
prefers-reduced-motion.

The boxless cards (stack, stats) come in a dark and a light variant; the README
picks one with <picture> and prefers-color-scheme, which follows the
viewer's GitHub theme.

Stats come from the public GitHub API. GITHUB_TOKEN is used for GraphQL when
present (the workflow provides one); locally it falls back to `gh auth token`.
"""

import json
import math
import os
import random
import re
import subprocess
import urllib.request
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "scripts", "fonts")
OUT = os.path.join(ROOT, "assets")

USER = "netgian"
STACK = "py,ts,js,php,cpp,astro,nextjs,react,nodejs,vercel,pytorch,sklearn"
STACK_NAMES = "Python, TypeScript, JavaScript, PHP, C++, Astro, Next.js, React, Node.js, Vercel, PyTorch, scikit-learn"
UA = {"User-Agent": "readme-assets-builder"}

# Graphite + violet
THEMES = {
    "dark": {
        "bg": "#0a0a0c",
        "panel": "#121216",
        "line": "#26262c",
        "text": "#ededf0",
        "dim": "#8b8b96",
        "accent": "#a78bfa",
        "track": "#1c1c21",
        "langs": ["#a78bfa", "#c4b5fd", "#6b6b78", "#45454f"],
    },
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f6f8",
        "line": "#e4e4e7",
        "text": "#18181b",
        "dim": "#6b6b76",
        "accent": "#7c3aed",
        "track": "#ececf0",
        "langs": ["#7c3aed", "#a78bfa", "#9a9aa5", "#c8c8d0"],
    },
}
D = THEMES["dark"]


# ------------------------------------------------------------------ text
class Font:
    def __init__(self, name):
        self.f = TTFont(os.path.join(FONTS, name + ".woff2"))
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.upm = self.f["head"].unitsPerEm
        self.hmtx = self.f["hmtx"]

    def width(self, s, size, tracking=0.0):
        w = sum(self.hmtx[self.cmap[ord(c)]][0] for c in s) * size / self.upm
        return w + tracking * max(len(s) - 1, 0)

    def path(self, s, size, x, y, tracking=0.0):
        k = size / self.upm
        pen = SVGPathPen(self.gs)
        for c in s:
            g = self.cmap[ord(c)]
            self.gs[g].draw(TransformPen(pen, (k, 0, 0, -k, x, y)))
            x += self.hmtx[g][0] * k + tracking
        return pen.getCommands()


INTER = Font("inter-latin-400-normal")
INTER_SB = Font("inter-latin-600-normal")
INTER_XB = Font("inter-latin-800-normal")
MONO = Font("jetbrains-mono-latin-500-normal")


def text(font, s, size, x, y, fill, anchor="start", tracking=0.0):
    w = font.width(s, size, tracking)
    x -= {"start": 0, "middle": w / 2, "end": w}[anchor]
    return f'<path fill="{fill}" d="{font.path(s, size, x, y, tracking)}"/>', w


REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


def pretty(markup):
    """One element per line, so the generated files diff cleanly."""
    return re.sub(r">\s*<", ">\n<", markup).strip() + "\n"


def round_nums(s):
    return re.sub(r"-?\d+\.\d+", lambda m: f"{float(m.group()):.1f}".rstrip("0").rstrip("."), s)


def svg(w, h, body, style, title, raw=""):
    title = escape(title, {'"': "&quot;"})
    return pretty(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{title}">'
        f"<title>{title}</title><style>{style}{REDUCED}</style>{round_nums(body)}{raw}</svg>"
    )


def section_label(t, s, w):
    p, lw = text(MONO, s, 18, 0, 30, t["accent"], tracking=2.5)
    return (
        p
        + f'<rect x="{lw + 16:.1f}" y="24" width="{w - lw - 16:.1f}" height="1" fill="{t["line"]}"/>'
    )


RISE = "@keyframes rise{from{opacity:0;transform:translateY(8px)}}"


# ------------------------------------------------------------------ banner
def rain(w, h, n, seed):
    rnd = random.Random(seed)
    drops, css = [], []
    for i in range(n):
        x = rnd.uniform(-0.2 * w, 1.15 * w)
        length = rnd.uniform(40, 120)
        dur = rnd.uniform(1.8, 3.8)
        op = rnd.uniform(0.12, 0.4)
        drops.append(
            f'<line class="r{i}" x1="{x:.1f}" y1="{-length:.1f}" x2="{x - 0.35 * length:.1f}" y2="0" '
            f'stroke="url(#drop)" stroke-width="{rnd.choice([1, 1, 1.5])}" stroke-linecap="round" opacity="{op:.2f}"/>'
        )
        css.append(
            f".r{i}{{animation:fall {dur:.2f}s linear {-rnd.uniform(0, dur):.2f}s infinite}}"
        )
    css.append(
        "@keyframes fall{from{transform:translate(0,0)}"
        f"to{{transform:translate({-0.35 * (h + 160):.1f}px,{h + 160}px)}}}}"
    )
    return '<g clip-path="url(#card)">' + "".join(drops) + "</g>", "".join(css)


def banner():
    W, H = 1280, 320
    a, line = D["accent"], D["line"]
    body = [
        f"""<defs>
<clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>
<linearGradient id="drop" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}" stop-opacity="0"/><stop offset="1" stop-color="{a}"/></linearGradient>
<radialGradient id="glow" cx="0.83" cy="0.5" r="0.5"><stop offset="0" stop-color="{a}" stop-opacity="0.16"/><stop offset="1" stop-color="{a}" stop-opacity="0"/></radialGradient>
<linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{a}" stop-opacity="0"/><stop offset="1" stop-color="{a}" stop-opacity="0.4"/></linearGradient>
<pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#ffffff" opacity="0.07"/></pattern>
</defs>""",
        f'<rect width="{W}" height="{H}" rx="18" fill="{D["bg"]}"/>',
        f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="url(#dots)"/>'
        f'<rect class="breathe" width="{W}" height="{H}" fill="url(#glow)"/></g>',
    ]
    drops, style = rain(W, H, 38, 7)
    body.append(drops)
    style += (
        ".sweep{animation:spin 5s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}"
        ".blip{opacity:0;animation:blip 5s ease-out infinite}"
        ".b0{animation-delay:.7s}.b1{animation-delay:2.6s}.b2{animation-delay:1.4s}.b3{animation-delay:4s}"
        "@keyframes blip{0%{opacity:0}4%{opacity:1}60%,100%{opacity:0}}"
        ".breathe{animation:breathe 6s ease-in-out infinite}@keyframes breathe{0%,100%{opacity:.7}50%{opacity:1}}"
        ".cursor{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
    )

    cx, cy, R = 1060, H / 2, 112
    radar = [f'<g transform="translate({cx} {cy})">']
    for rr in (R, R * 0.66, R * 0.33):
        radar.append(f'<circle r="{rr:.1f}" fill="none" stroke="#ffffff" stroke-opacity="0.12"/>')
    radar.append(f'<path d="M{-R} 0H{R}M0 {-R}V{R}" stroke="#ffffff" stroke-opacity="0.07"/>')
    for ang in range(0, 360, 15):
        radar.append(
            f'<line y1="{-R}" y2="{-R + (8 if ang % 45 == 0 else 4)}" stroke="#ffffff" '
            f'stroke-opacity="{0.35 if ang % 45 == 0 else 0.18}" transform="rotate({ang})"/>'
        )
    a0 = math.radians(-60)
    radar.append(
        f'<g class="sweep"><path d="M0 0L{R * math.cos(a0):.1f} {R * math.sin(a0):.1f}A{R} {R} 0 0 1 {R} 0Z" '
        f'fill="url(#sweep)"/><line x2="{R}" stroke="{a}" stroke-width="1.5"/></g>'
    )
    for i, (bx, by) in enumerate([(50, -36), (-60, 28), (22, 66), (-28, -74)]):
        radar.append(f'<circle class="blip b{i}" cx="{bx}" cy="{by}" r="3.5" fill="{a}"/>')
    radar.append(f'<circle r="3.5" fill="{D["text"]}"/></g>')
    body.append("".join(radar))

    x0 = 76
    p, w = text(MONO, "netgian@github:~$ whoami", 21, x0, 104, D["dim"])
    body.append(
        p + f'<rect class="cursor" x="{x0 + w + 8:.1f}" y="87" width="11" height="21" fill="{a}"/>'
    )
    body.append(text(INTER_XB, "Gian Glen", 104, x0 - 4, 208, D["text"], tracking=-3.5)[0])
    p, w = text(INTER_SB, "AI Engineering", 32, x0, 262, D["dim"])
    body.append(p + f'<circle cx="{x0 + w + 19:.1f}" cy="251" r="4" fill="{a}"/>')
    body.append(text(INTER_SB, "AI Security", 32, x0 + w + 38, 262, a)[0])
    body.append(
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="17.5" fill="none" stroke="{line}"/>'
    )
    return svg(W, H, "".join(body), style, "Gian Glen. AI Engineering, AI Security.")


# ------------------------------------------------------------------ stack + stats (boxless)
CW, CH = 620, 340


def fetch(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def stack_card(t, mode):
    icons = fetch(f"https://skillicons.dev/icons?i={STACK}&perline=4&theme={mode}").strip()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', icons).group(1).split()]
    top, area_h = 64, CH - 64 - 24
    iw = vb[2] * area_h / vb[3]
    icons = re.sub(
        r'<svg[^>]*?width="[^"]*" height="[^"]*"',
        f'<svg x="{(CW - 48 - iw) / 2:.1f}" y="{top}" width="{iw:.1f}" height="{area_h:.1f}"',
        icons,
        count=1,
    )
    body = (
        section_label(t, "STACK", CW - 48)
        + f'<rect x="{CW - 1}" y="64" width="1" height="{CH - 88}" fill="{t["line"]}"/>'
    )
    style = ".rise{animation:rise .9s cubic-bezier(.2,.8,.2,1) both}" + RISE
    return svg(CW, CH, body, style, "Stack: " + STACK_NAMES, raw=f'<g class="rise">{icons}</g>')


def github_stats():
    token = (
        os.environ.get("GITHUB_TOKEN")
        or subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    query = """query($login:String!){ user(login:$login){
      repositories(ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC, first:100){
        totalCount nodes{ stargazerCount forkCount
          languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name } } } } } } }"""
    u = json.loads(
        fetch(
            "https://api.github.com/graphql",
            {"Authorization": f"bearer {token}"},
            json.dumps({"query": query, "variables": {"login": USER}}).encode(),
        )
    )["data"]["user"]
    repos = u["repositories"]["nodes"]
    langs = {}
    for repo in repos:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    shares = [(n, s / total) for n, s in top[:3]]
    rest = 1 - sum(s for _, s in shares)
    if rest > 0.005:
        shares.append(("Other", rest))
    return {
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": u["repositories"]["totalCount"],
        "forks": sum(r["forkCount"] for r in repos),
        "langs": shares,
    }


def compact(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def stats_card(t, st):
    x0 = 48
    w = CW - x0
    body = [f'<g transform="translate({x0} 0)">' + section_label(t, "GITHUB STATS", w) + "</g>"]
    style = [".rise{animation:rise .8s cubic-bezier(.2,.8,.2,1) both}", RISE]
    metrics = [("stars", st["stars"]), ("repos", st["repos"]), ("forks", st["forks"])]
    col = w / 3
    for i, (label, value) in enumerate(metrics):
        x = x0 + i * col
        num, _ = text(INTER_XB, compact(value), 60, x - 2, 132, t["text"], tracking=-1.5)
        lab, _ = text(INTER, label, 22, x, 166, t["dim"])
        body.append(f'<g class="rise m{i}">{num}{lab}</g>')
        style.append(f".m{i}{{animation-delay:{0.08 + i * 0.1:.2f}s}}")

    name_w = 112
    bar_x = x0 + name_w
    pct_w = 64
    bar_w = w - name_w - pct_w - 8
    for i, (name, share) in enumerate(st["langs"]):
        y = 222 + i * 36
        body.append(text(INTER_SB, name, 21, x0, y, t["text"])[0])
        body.append(
            f'<rect x="{bar_x}" y="{y - 10}" width="{bar_w}" height="8" rx="4" fill="{t["track"]}"/>'
        )
        body.append(
            f'<rect class="grow g{i}" x="{bar_x}" y="{y - 10}" width="{max(bar_w * share, 6):.1f}" '
            f'height="8" rx="4" fill="{t["langs"][i]}"/>'
        )
        body.append(text(INTER, f"{share * 100:.0f}%", 21, CW, y, t["dim"], anchor="end")[0])
        style.append(f".g{i}{{animation-delay:{0.35 + i * 0.12:.2f}s}}")
    style.append(
        ".grow{transform-box:fill-box;transform-origin:left;animation:grow 1.1s cubic-bezier(.2,.8,.2,1) both}"
        "@keyframes grow{from{transform:scaleX(0)}}"
    )
    summary = (
        f"GitHub stats: {st['stars']} stars, {st['repos']} public repositories, {st['forks']} forks. "
        "Languages: " + ", ".join(f"{n} {s * 100:.0f}%" for n, s in st["langs"])
    )
    return svg(CW, CH, "".join(body), "".join(style), summary)


# ------------------------------------------------------------------ contact + divider
ICONS = {
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/>',
}


def contact(t, icon, label, value):
    W, H = 400, 96
    body = [
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{t["panel"]}" stroke="{t["line"]}"/>',
        f'<rect class="ring" x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["accent"]}"/>',
        f'<g transform="translate(32 34) scale(1.15)" fill="none" stroke="{t["accent"]}" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>',
        text(MONO, label, 16, 84, 40, t["dim"], tracking=1.8)[0],
        text(INTER_SB, value, 26, 84, 72, t["text"])[0],
        f'<g class="arrow" fill="none" stroke="{t["dim"]}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round"><path d="M352 48h20M364 40l8 8-8 8"/></g>',
    ]
    style = (
        ".ring{opacity:0;animation:ring 4s ease-in-out infinite}@keyframes ring{0%,100%{opacity:0}50%{opacity:.8}}"
        ".arrow{animation:nudge 2s ease-in-out infinite}@keyframes nudge{50%{transform:translateX(4px)}}"
    )
    return svg(W, H, "".join(body), style, f"{label.title()}: {value}")


def divider():
    W, H = 1280, 24
    a = "#a78bfa"
    body = (
        f'<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{a}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{a}"/><stop offset="1" stop-color="{a}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect y="11.5" width="{W}" height="1" fill="url(#g)" opacity=".45"/>'
        f'<rect class="pulse" x="{W / 2 - 4}" y="8" width="8" height="8" fill="{a}" transform="rotate(45 {W / 2} 12)"/>'
    )
    style = ".pulse{animation:pulse 2.4s ease-in-out infinite}@keyframes pulse{0%,100%{opacity:.3}50%{opacity:1}}"
    return svg(W, H, body, style, "divider")


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.endswith(".svg"):
            os.remove(os.path.join(OUT, old))
    st = github_stats()
    files = {"banner.svg": banner(), "divider.svg": divider()}
    for mode, t in THEMES.items():
        files[f"stack-{mode}.svg"] = stack_card(t, mode)
        files[f"stats-{mode}.svg"] = stats_card(t, st)
    # Contact cards are links, and GitHub drops <picture> inside <a>, so they
    # get a single dark variant that reads on both themes (like the banner).
    files["contact-web.svg"] = contact(D, "globe", "WEBSITE", "gianlopez.es")
    files["contact-linkedin.svg"] = contact(D, "linkedin", "LINKEDIN", "in/gianglen")
    files["contact-email.svg"] = contact(D, "mail", "EMAIL", "hi@gianlopez.es")
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print(f"{name}: {len(content) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
