#!/usr/bin/env python3
"""Fit the 'top' bot from the best verified games of the online leaderboards.

    python3 tools/fit_community.py                 # the last 4 weeks, the best 12 games
    python3 tools/fit_community.py --weeks 8 --best 20 --difficulty adventure

Verified games are archived by the verifier (tools/verify_runs.py) as assets of
the pre-releases recordings-YYYY-Www of the repository, named
<difficulty>-<score>-<id>.json.gz. This downloads the best of the last weeks
(public: no token needed), measures them with the code of their version and
fits a bot to them (tools/fit_bot.py), written to src/sim/top_profile.json:
the bot profile 'top' plays like the best players (tools/simulate.py --bot top,
game.py --bot top). .github/workflows/community-bot.yml runs it every week.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = 'Onheiron/PY-birds-vs-bats'
OUT = ROOT / 'src' / 'sim' / 'top_profile.json'


def _get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'BVB-fit', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed https host)
        return response.read()


def archived(weeks):
    """[(score, difficulty, name, url)] of the verified games of the last ``weeks`` weeks."""
    releases = json.loads(_get(f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100'))
    recent = sorted((r for r in releases if r['tag_name'].startswith('recordings-')), key=lambda r: r['tag_name'])
    games = []
    for release in recent[-weeks:]:
        for asset in release.get('assets', []):
            parts = asset['name'].split('-', 2)
            if len(parts) == 3 and parts[1].isdigit():
                games.append((int(parts[1]), parts[0], asset['name'], asset['browser_download_url']))
    return games


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--weeks', type=int, default=4)
    parser.add_argument('--best', type=int, default=12, help='how many of the best games')
    parser.add_argument('--difficulty', default='adventure', help="a difficulty, or 'all'")
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args()

    games = [g for g in archived(args.weeks) if args.difficulty == 'all' or g[1] == args.difficulty]
    best = sorted(games, reverse=True)[: args.best]
    if not best:
        raise SystemExit('No verified games archived yet: nothing to fit.')
    folder = Path(tempfile.mkdtemp(prefix='bvb-top-'))
    for score, difficulty, name, url in best:
        (folder / name).write_bytes(_get(url))
        print(f'{name}: {score:,} on {difficulty}')
    files = [str(path) for path in sorted(folder.glob('*.json.gz'))]
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'fit_bot.py'), *files, '--out', args.out], check=True)


if __name__ == '__main__':
    main()
