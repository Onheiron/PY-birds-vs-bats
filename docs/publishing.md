# Publishing BVB

Every release (`.github/workflows/release.yml`, run by hand with "publish", or
a pushed tag `v<version>`) builds the game and publishes it:

| Where | What | How |
|---|---|---|
| GitHub release | binaries for Linux, macOS, Windows, the Steam Linux build, the pip package | always |
| PyPI | `pip install birds-vs-bats`, the `bvb` command | trusted publishing (no token) |
| itch.io | channels `linux` (also the Steam Deck), `mac`, `windows` | butler, with an API key |

Before a release, raise `__version__` in `src/__init__.py`: PyPI and itch.io
refuse a version they already have.

## PyPI, once

The project `birds-vs-bats` on pypi.org must trust this workflow:

1. pypi.org → your projects → **birds-vs-bats** → **Manage** → **Publishing**
   → **Add a new publisher** (GitHub):
   - owner `Onheiron`, repository `PY-birds-vs-bats`,
   - workflow `release.yml`, environment `pypi`.
2. On GitHub: repository → Settings → **Environments** → **New environment**
   `pypi` (no secret needed; you may require your approval before it runs).

No token is stored anywhere: PyPI checks that the upload comes from that
workflow.

The pip package (`pyproject.toml`) installs one package, `birds_vs_bats`:
a launcher (`packaging/pip/birds_vs_bats/`) and the game laid out as in the
repository (`src/`, `game.py`, the configuration files, `media/music` and
`media/fonts`). `bvb` runs it. To try it locally:

```bash
python3 -m build
```

```bash
pip install dist/birds_vs_bats-*.whl
```

## itch.io, once

1. Create the game on itch.io (Dashboard → **Create new project**): kind
   *Downloadable*, pricing *No payments* or *Donate* ("pay what you want",
   0 € minimum). Its address is `https://<user>.itch.io/<game>`.
2. Make a butler API key: itch.io → Settings → **API keys** → *Generate new
   API key*.
3. On GitHub: repository → Settings → **Secrets and variables** → Actions:
   - secret `BUTLER_API_KEY`: the key;
   - variable `ITCH_GAME`: `<user>/<game>` (for example `onheiron/birds-vs-bats`).

From the next release the builds are pushed to the channels `linux`, `mac`
and `windows`; itch.io tags them by platform from the channel name. The itch
app installs them and updates them by itself; on the Steam Deck, add the
installed `BVB` to Steam as a non-Steam game once.

Without `ITCH_GAME` the itch.io step is skipped.
