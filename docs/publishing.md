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
workflow. Instead, a PyPI API token scoped to the project can be saved as the
repository secret `PYPI_API_TOKEN` (Settings → Secrets and variables →
Actions); the release uses it when it is there.

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

To push the builds of a release already published (the first time, or again),
run the workflow **itch.io** (Actions → itch.io → Run workflow). From the next
release on, the builds are pushed to the channels `linux`, `mac`
and `windows`; itch.io tags them by platform from the channel name. The itch
app installs them and updates them by itself; on the Steam Deck, add the
installed `BVB` to Steam as a non-Steam game once.

Without `ITCH_GAME` the itch.io step is skipped.

## Updates of the downloaded builds

The desktop builds and the Steam Linux build update themselves
(`src/services/updater.py`): at the title they ask GitHub for the latest
release; when it is newer, UPDATE in the title menu downloads the build of the
same kind (the `BUILD` file the specs write into the bundle), checks it against
the release's `SHA256SUMS.txt`, swaps it in and RESTART starts it. So the asset
names of the release (`BVB-<version>-<kind>.tar.gz` / `.zip`) must not change.
It is off from the sources and pip, when Steam installed the game, and with
`BVB_NO_UPDATE` set.
