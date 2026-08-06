#!/usr/bin/env python3
"""Generate the profile README's SVG assets from live GitHub data.

Why this exists
---------------
Every popular profile-README widget (github-readme-stats, profile-trophy,
streak-stats, capsule-render, readme-typing-svg) is a shared free Vercel/Heroku
instance. They rate-limit, lapse on billing, and intermittently return HTTP 200
with an empty body -- which renders as a broken image. GitHub's camo proxy then
caches that failure, so the image stays broken long after the upstream recovers.

This script removes the dependency: it pulls the data from GitHub's own API and
writes plain SVG files into assets/, which the README references by relative
path. GitHub serves them from the repo itself, so they cannot 503.

Stdlib only, so CI needs no pip install. Runs unauthenticated; set GITHUB_TOKEN
to get the higher rate limit in Actions.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "shivaganeshtalikota")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

# Palette — matches the README's indigo/violet scheme, tuned to read on both
# GitHub themes (the cards carry their own dark background).
BG = "#0d1117"
BORDER = "#26304a"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#a78bfa"
ACCENT2 = "#818cf8"
DEEP = "#7c3aed"

FONT = "'Segoe UI',Ubuntu,'Helvetica Neue',Helvetica,sans-serif"
MONO = "'JetBrains Mono','Fira Code',ui-monospace,'SF Mono',Consolas,monospace"

# GitHub's own language colours, for the languages we actually use.
LANG_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Java": "#b07219",
    "Kotlin": "#A97BFF",
    "Solidity": "#AA6746",
    "C": "#555555",
    "C++": "#f34b7d",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Jupyter Notebook": "#DA5B0B",
    "Shell": "#89e051",
    "Dart": "#00B4AB",
    "Go": "#00ADD8",
}


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

def _get(url: str, raw: bool = False):
    headers = {
        "User-Agent": f"{USER}-profile-generator",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        body = resp.read().decode("utf-8", "replace")
    return body if raw else json.loads(body)


def fetch_profile() -> dict:
    """Collect the numbers we're willing to show. Deliberately no star or
    follower count: on a young account those read as weak, and a metric that
    undersells you is worse than no metric."""
    user = _get(f"https://api.github.com/users/{USER}")
    repos = _get(f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed")

    owned = [r for r in repos if not r.get("fork")]

    # Language mix, weighted by actual bytes rather than repo count, so one
    # tiny throwaway repo doesn't outweigh a real project.
    byte_totals: Counter[str] = Counter()
    for repo in owned:
        try:
            langs = _get(repo["languages_url"])
        except urllib.error.HTTPError:
            continue
        for name, count in langs.items():
            byte_totals[name] += count

    try:
        prs = _get(
            f"https://api.github.com/search/issues?q=author:{USER}+type:pr&per_page=1"
        ).get("total_count", 0)
    except urllib.error.HTTPError:
        prs = 0

    days, total_contribs = fetch_contributions()

    return {
        "name": user.get("name") or USER,
        "public_repos": user.get("public_repos", 0),
        "owned_repos": len(owned),
        "prs": prs,
        "languages": byte_totals,
        "days": days,
        "contributions": total_contribs,
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y"),
    }


def fetch_contributions() -> tuple[list[tuple[str, int, int, int]], int]:
    """Scrape the public contributions calendar. No token required, and it is
    the same data GitHub renders on the profile page.

    The calendar markup is row-major by weekday -- one <tr> per weekday, so the
    first seven cells are seven consecutive *Sundays*, not the first week. The
    cell id encodes the real grid position as
    contribution-day-component-<row>-<col>, so read it rather than inferring it
    from document order (inferring it column-major scrambles the month labels).
    """
    html = _get(f"https://github.com/users/{USER}/contributions", raw=True)

    days = [
        (m.group("date"), int(m.group("level")), int(m.group("row")), int(m.group("col")))
        for m in re.finditer(
            r'data-date="(?P<date>\d{4}-\d{2}-\d{2})"\s+'
            r'id="contribution-day-component-(?P<row>\d+)-(?P<col>\d+)"\s+'
            r'data-level="(?P<level>\d)"',
            html,
        )
    ]
    if not days:
        raise RuntimeError("could not parse the contributions calendar")

    total = 0
    m = re.search(r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year", html)
    if m:
        total = int(m.group(1).replace(",", ""))

    return days, total


# --------------------------------------------------------------------------
# svg helpers
# --------------------------------------------------------------------------

def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write(name: str, svg: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(svg.strip() + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}  ({path.stat().st_size:,} bytes)")


# --------------------------------------------------------------------------
# cards
# --------------------------------------------------------------------------

def render_header(data: dict) -> str:
    """Banner. Replaces capsule-render."""
    w, h = 1000, 200
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Shiva Ganesh Talikota, Product Development Engineer">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1020"/>
      <stop offset="45%" stop-color="#312e81"/>
      <stop offset="100%" stop-color="#6d28d9"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#a78bfa"/>
      <stop offset="100%" stop-color="#a78bfa" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <style>
    .sheen {{ animation: sweep 7s ease-in-out infinite; }}
    @keyframes sweep {{ 0% {{ transform: translateX(-45%); }} 100% {{ transform: translateX(115%); }} }}
    .fade {{ opacity: 0; animation: fade .9s ease-out forwards; }}
    .d1 {{ animation-delay: .15s; }} .d2 {{ animation-delay: .4s; }} .d3 {{ animation-delay: .65s; }}
    @keyframes fade {{ to {{ opacity: 1; }} }}
    .dot {{ animation: pulse 2.4s ease-in-out infinite; }}
    @keyframes pulse {{ 0%,100% {{ opacity: .35; }} 50% {{ opacity: 1; }} }}
  </style>

  <rect width="{w}" height="{h}" fill="url(#bg)"/>
  <g opacity="0.35">
    <path d="M0 150 Q 250 110 500 148 T 1000 132 V200 H0 Z" fill="#0b1020" opacity="0.55"/>
    <path d="M0 168 Q 250 138 500 170 T 1000 156 V200 H0 Z" fill="#0b1020" opacity="0.8"/>
  </g>
  <rect class="sheen" width="320" height="{h}" fill="url(#sheen)"/>

  <text class="fade d1" x="60" y="82" font-family="{FONT}" font-size="42" font-weight="700" fill="#ffffff">Shiva Ganesh Talikota</text>
  <rect class="fade d2" x="60" y="98" width="230" height="2" fill="url(#rule)"/>
  <text class="fade d2" x="60" y="128" font-family="{FONT}" font-size="18" font-weight="600" fill="#c7d2fe">Product Development Engineer</text>
  <text class="fade d3" x="60" y="154" font-family="{MONO}" font-size="13.5" fill="#a5b4fc">Applied AI &#183; retrieval systems &#183; full-stack product</text>

  <g class="fade d3" transform="translate(830,60)">
    <circle class="dot" cx="0" cy="0" r="4" fill="#4ade80"/>
    <text x="14" y="4.5" font-family="{MONO}" font-size="12.5" fill="#bbf7d0">open to 2026 roles</text>
  </g>
</svg>
"""


def render_typing(data: dict) -> str:
    """Typed-text animation. Replaces readme-typing-svg."""
    lines = [
        "Product Development Engineer @ matriXO",
        "RAG pipelines, agentic workflows, shipped products",
        "Python · TypeScript · Next.js · PyTorch",
        "B.Tech CSE (AI & ML) '26 · Hyderabad, India",
    ]
    w, h = 760, 46
    per = 3.6                      # seconds each line is on screen
    total = per * len(lines)
    char_w = 11.1                  # approx advance for the mono size below

    css, body = [], []
    for i, line in enumerate(lines):
        width = len(line) * char_w
        start = (per * i) / total * 100
        typed = start + (1.5 / total * 100)     # finished typing
        held = start + (3.0 / total * 100)      # starts clearing
        end = start + (per / total * 100)

        # The caret and the reveal share identical keyframe stops and timing
        # function, so the caret tracks the last typed character instead of
        # parking at the end of the line.
        steps = f"steps({len(line)},end)"
        css.append(
            f"""
    #clip{i} rect {{ animation: type{i} {total}s {steps} infinite; }}
    @keyframes type{i} {{
      0%, {start:.3f}% {{ width: 0; }}
      {typed:.3f}%, {held:.3f}% {{ width: {width:.1f}px; }}
      {end:.3f}%, 100% {{ width: 0; }}
    }}
    #cur{i} {{ opacity: 0; animation: cur{i} {total}s {steps} infinite; }}
    @keyframes cur{i} {{
      0%, {start:.3f}% {{ opacity: 0; transform: translateX(0); }}
      {start + 0.001:.3f}% {{ opacity: 1; transform: translateX(0); }}
      {typed:.3f}%, {held:.3f}% {{ opacity: 1; transform: translateX({width:.1f}px); }}
      {end - 0.001:.3f}% {{ opacity: 1; transform: translateX(0); }}
      {end:.3f}%, 100% {{ opacity: 0; transform: translateX(0); }}
    }}"""
        )
        body.append(
            f"""
  <clipPath id="clip{i}"><rect x="0" y="0" width="0" height="{h}"/></clipPath>
  <g clip-path="url(#clip{i})">
    <text x="0" y="30" font-family="{MONO}" font-size="17" font-weight="600" fill="{ACCENT}">{esc(line)}</text>
  </g>
  <rect id="cur{i}" x="0" y="12" width="2" height="22" fill="{ACCENT2}"/>"""
        )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(' / '.join(lines))}">
  <style>{''.join(css)}
  </style>
  {''.join(body)}
</svg>
"""


def render_stats(data: dict) -> str:
    """Key metrics. Replaces the github-readme-stats card."""
    w, h = 480, 195
    langs = data["languages"]
    top_lang = langs.most_common(1)[0][0] if langs else "Python"

    metrics = [
        ("Contributions", f"{data['contributions']:,}", "last 12 months"),
        ("Pull requests", f"{data['prs']:,}", "opened"),
        ("Repositories", f"{data['owned_repos']:,}", "public, authored"),
        ("Primary language", top_lang, "by volume"),
    ]

    rows = []
    for i, (label, value, sub) in enumerate(metrics):
        y = 74 + i * 28
        rows.append(
            f"""
  <g class="row r{i}">
    <circle cx="30" cy="{y - 5}" r="3" fill="{ACCENT}"/>
    <text x="44" y="{y}" font-family="{FONT}" font-size="13.5" fill="{MUTED}">{esc(label)}</text>
    <text x="300" y="{y}" font-family="{MONO}" font-size="15" font-weight="700" fill="{TEXT}" text-anchor="end">{esc(value)}</text>
    <text x="312" y="{y}" font-family="{FONT}" font-size="11" fill="#6b7280">{esc(sub)}</text>
  </g>"""
        )

    delays = "".join(
        f"    .r{i} {{ animation-delay: {0.12 * i + 0.15:.2f}s; }}\n" for i in range(len(metrics))
    )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub activity summary">
  <style>
    .row {{ opacity: 0; animation: slide .6s ease-out forwards; }}
{delays}    @keyframes slide {{ from {{ opacity: 0; transform: translateX(-8px); }} to {{ opacity: 1; transform: translateX(0); }} }}
  </style>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="34" font-family="{FONT}" font-size="15.5" font-weight="700" fill="{ACCENT}">GitHub Activity</text>
  <text x="24" y="52" font-family="{MONO}" font-size="10.5" fill="#6b7280">@{USER} &#183; refreshed {esc(data['generated'])}</text>
  <line x1="24" y1="60" x2="{w - 24}" y2="60" stroke="{BORDER}"/>
{''.join(rows)}
</svg>
"""


def render_languages(data: dict) -> str:
    """Language split by bytes. Replaces the top-langs card."""
    w, h = 480, 195
    # Anything under 1% is config noise (a stray Batchfile, a CI PowerShell
    # script) and reads as padding on a card a recruiter is scanning.
    grand = sum(data["languages"].values()) or 1
    langs = [(n, c) for n, c in data["languages"].most_common(6) if c / grand >= 0.01]
    total = sum(c for _, c in langs) or 1

    bar_x, bar_w, bar_y = 24, w - 48, 74
    segs, legend, offset = [], [], 0.0

    for i, (name, count) in enumerate(langs):
        frac = count / total
        seg_w = frac * bar_w
        color = LANG_COLORS.get(name, ACCENT2)
        segs.append(
            f'  <rect class="seg s{i}" x="{bar_x + offset:.2f}" y="{bar_y}" '
            f'width="{max(seg_w - 1.5, 1):.2f}" height="12" rx="2" fill="{color}"/>'
        )
        offset += seg_w

        col, row = i % 2, i // 2
        lx = 26 + col * 224
        ly = 118 + row * 25
        legend.append(
            f"""
  <g class="seg s{i}">
    <circle cx="{lx + 4}" cy="{ly - 4}" r="4.5" fill="{color}"/>
    <text x="{lx + 16}" y="{ly}" font-family="{FONT}" font-size="12.5" fill="{TEXT}">{esc(name)}</text>
    <text x="{lx + 200}" y="{ly}" font-family="{MONO}" font-size="12" fill="{MUTED}" text-anchor="end">{frac * 100:.1f}%</text>
  </g>"""
        )

    delays = "".join(
        f"    .s{i} {{ animation-delay: {0.09 * i + 0.15:.2f}s; }}\n" for i in range(len(langs))
    )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Language distribution across public repositories">
  <style>
    .seg {{ opacity: 0; animation: pop .55s ease-out forwards; }}
{delays}    @keyframes pop {{ from {{ opacity: 0; transform: translateY(5px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  </style>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="34" font-family="{FONT}" font-size="15.5" font-weight="700" fill="{ACCENT}">Languages</text>
  <text x="24" y="52" font-family="{MONO}" font-size="10.5" fill="#6b7280">by bytes written across public repos</text>
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="12" rx="2" fill="#161b22"/>
{chr(10).join(segs)}
{''.join(legend)}
</svg>
"""


def render_activity(data: dict) -> str:
    """Contribution heatmap. Replaces the activity-graph widget."""
    days = data["days"]
    cell, gap = 11, 3
    pitch = cell + gap
    grid_x, grid_y = 48, 58

    rows = max(d[2] for d in days) + 1
    cols = max(d[3] for d in days) + 1
    w = grid_x + cols * pitch + 20
    h = grid_y + rows * pitch + 40      # leave room for the legend below

    shades = ["#161b22", "#38246b", "#5b2fb0", "#7c3aed", "#a78bfa"]

    squares, month_labels, seen = [], [], set()
    for date, level, row, col in days:
        x = grid_x + col * pitch
        y = grid_y + row * pitch
        squares.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" '
            f'fill="{shades[level]}" class="c" style="animation-delay:{col * 0.006:.3f}s"><title>{date}</title></rect>'
        )

        # Label a month at the first column whose top-row date falls in it.
        dt = datetime.strptime(date, "%Y-%m-%d")
        key = (dt.year, dt.month)
        if row == 0 and key not in seen:
            seen.add(key)
            month_labels.append(
                f'<text x="{x}" y="50" font-family="{FONT}" font-size="10" fill="{MUTED}">{dt.strftime("%b")}</text>'
            )

    day_labels = "".join(
        f'<text x="{grid_x - 8}" y="{grid_y + i * pitch + 9}" font-family="{FONT}" font-size="9.5" fill="{MUTED}" text-anchor="end">{lbl}</text>'
        for i, lbl in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )

    legend_y = grid_y + rows * pitch + 20
    legend_x = w - 150
    legend = "".join(
        f'<rect x="{legend_x + 32 + i * 15}" y="{legend_y - 9}" width="{cell}" height="{cell}" rx="2.5" fill="{s}"/>'
        for i, s in enumerate(shades)
    )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{data['contributions']} contributions in the last year">
  <style>
    .c {{ opacity: 0; animation: in .5s ease-out forwards; }}
    @keyframes in {{ from {{ opacity: 0; transform: scale(.4); transform-origin: center; }} to {{ opacity: 1; transform: scale(1); }} }}
  </style>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="30" font-family="{FONT}" font-size="15.5" font-weight="700" fill="{ACCENT}">{data['contributions']:,} contributions in the last year</text>
  {''.join(month_labels)}
  {day_labels}
  {''.join(squares)}
  <text x="{legend_x}" y="{legend_y}" font-family="{FONT}" font-size="10" fill="{MUTED}">Less</text>
  {legend}
  <text x="{legend_x + 114}" y="{legend_y}" font-family="{FONT}" font-size="10" fill="{MUTED}">More</text>
</svg>
"""


def render_footer(data: dict) -> str:
    w, h = 1000, 110
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Building from Hyderabad, India">
  <defs>
    <linearGradient id="fg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#6d28d9"/>
      <stop offset="55%" stop-color="#312e81"/>
      <stop offset="100%" stop-color="#0b1020"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#fg)"/>
  <path d="M0 30 Q 250 62 500 30 T 1000 34 V0 H0 Z" fill="{BG}" opacity="0.65"/>
  <path d="M0 14 Q 250 46 500 12 T 1000 18 V0 H0 Z" fill="{BG}"/>
  <text x="{w // 2}" y="82" text-anchor="middle" font-family="{MONO}" font-size="13" fill="#c7d2fe">Building from Hyderabad, India &#183; open to 2026 roles</text>
</svg>
"""


def main() -> int:
    print(f"Fetching GitHub data for @{USER} ...")
    try:
        data = fetch_profile()
    except urllib.error.HTTPError as exc:
        print(f"GitHub API error: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error: {exc.reason}", file=sys.stderr)
        return 1

    print(
        f"  {data['contributions']:,} contributions | {data['prs']} PRs | "
        f"{data['owned_repos']} authored repos | {len(data['languages'])} languages"
    )

    print("Rendering assets ...")
    write("header.svg", render_header(data))
    write("typing.svg", render_typing(data))
    write("stats.svg", render_stats(data))
    write("languages.svg", render_languages(data))
    write("activity.svg", render_activity(data))
    write("footer.svg", render_footer(data))
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
