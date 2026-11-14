"""Generate GitHub stats and top-languages SVG cards for the profile README.

Usage: python scripts/gen_cards.py <username> <out_dir>
Needs GITHUB_TOKEN in the environment. Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

ACCENT = "#3B82F6"
TEXT = "#E6EDF3"
MUTED = "#8B949E"
BORDER = "#30363D"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif"
LANG_COLORS = ["#3B82F6", "#22C55E", "#F59E0B", "#A855F7", "#EF4444", "#14B8A6"]

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    name
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE]) { totalCount }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def graphql(token: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def collect(login: str, token: str) -> dict:
    stars, langs, cursor, first = 0, {}, None, None
    while True:
        user = graphql(token, {"login": login, "cursor": cursor})
        first = first or user
        repos = user["repositories"]
        for repo in repos["nodes"]:
            stars += repo["stargazerCount"]
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                langs[name] = langs.get(name, 0) + edge["size"]
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    cc = first["contributionsCollection"]
    return {
        "name": first["name"] or login,
        "stats": [
            ("Total stars", stars),
            ("Commits (last year)", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
            ("Pull requests", first["pullRequests"]["totalCount"]),
            ("Issues", first["issues"]["totalCount"]),
            ("Contributed to", first["repositoriesContributedTo"]["totalCount"]),
            ("Public repos", first["repositories"]["totalCount"]),
        ],
        "langs": langs,
    }


def card(width: int, height: int, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" '
        f'fill="none" stroke="{BORDER}"/>'
        f'<text x="24" y="38" fill="{ACCENT}" font-family="{FONT}" font-size="17" '
        f'font-weight="600">{escape(title)}</text>{body}</svg>'
    )


def stats_svg(data: dict) -> str:
    rows = []
    for i, (label, value) in enumerate(data["stats"]):
        y = 74 + i * 25
        rows.append(
            f'<text x="24" y="{y}" fill="{MUTED}" font-family="{FONT}" font-size="14">'
            f"{escape(label)}</text>"
            f'<text x="300" y="{y}" fill="{TEXT}" font-family="{FONT}" font-size="14" '
            f'font-weight="600" text-anchor="end">{value:,}</text>'
        )
    return card(330, 74 + 6 * 25, f"{data['name']}'s GitHub stats", "".join(rows))


def languages_svg(data: dict) -> str:
    top = sorted(data["langs"].items(), key=lambda kv: kv[1], reverse=True)[:6]
    total = sum(size for _, size in top) or 1
    width, bar_w = 330, 282
    parts, x = [], 24.0
    for i, (_, size) in enumerate(top):
        w = bar_w * size / total
        parts.append(f'<rect x="{x:.2f}" y="56" width="{w:.2f}" height="8" fill="{LANG_COLORS[i]}"/>')
        x += w
    bar = f'<clipPath id="r"><rect x="24" y="56" width="{bar_w}" height="8" rx="4"/></clipPath><g clip-path="url(#r)">{"".join(parts)}</g>'
    items = []
    for i, (name, size) in enumerate(top):
        cx, cy = (24 if i % 2 == 0 else 175), 92 + (i // 2) * 26
        items.append(
            f'<circle cx="{cx + 5}" cy="{cy - 5}" r="5" fill="{LANG_COLORS[i]}"/>'
            f'<text x="{cx + 16}" y="{cy}" fill="{TEXT}" font-family="{FONT}" font-size="13">'
            f'{escape(name)} <tspan fill="{MUTED}">{100 * size / total:.1f}%</tspan></text>'
        )
    return card(width, 74 + 6 * 25, "Most used languages", bar + "".join(items))


def main() -> None:
    login, out = sys.argv[1], Path(sys.argv[2])
    token = os.environ["GITHUB_TOKEN"]
    data = collect(login, token)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.svg").write_text(stats_svg(data), encoding="utf-8")
    (out / "languages.svg").write_text(languages_svg(data), encoding="utf-8")
    print(f"Wrote cards for {login}: {data['stats']}")


if __name__ == "__main__":
    main()
