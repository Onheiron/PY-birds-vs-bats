#!/usr/bin/env bash
# Build the Steam Linux depot inside the Steam Linux Runtime 3 "sniper" SDK,
# the environment Valve asks Linux games to be built in (it runs on the Steam
# Deck and on any distribution with Steam).
#
#   packaging/steam/build-linux.sh            # with docker (or podman)
#   packaging/steam/build-linux.sh --inside   # already inside the SDK (CI)
#
# Result: dist/BVB/ (the depot: BVB + _internal/) and
#         dist/BVB-<version>-steam-linux.tar.gz
set -euo pipefail
cd "$(dirname "$0")/../.."

IMAGE=registry.gitlab.steamos.cloud/steamrt/sniper/sdk:latest

if [ "${1:-}" != "--inside" ]; then
    engine=$(command -v docker || command -v podman)
    exec "$engine" run --rm -v "$PWD":/src -w /src "$IMAGE" packaging/steam/build-linux.sh --inside
fi

# The SDK's own Python is too old: a standalone CPython 3.12 (glibc 2.17+) via uv
if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv venv --python 3.12 /tmp/bvb-venv
# shellcheck disable=SC1091
. /tmp/bvb-venv/bin/activate
uv pip install -r requirements.txt pygame-ce numpy sounddevice pyinstaller

pyinstaller --noconfirm packaging/steam/BVB-Steam.spec
version=$(dist/BVB/BVB --version | cut -d' ' -f2)
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 10 dist/BVB/BVB --bot expert --speed 8 >/dev/null 2>&1 || [ $? -eq 124 ]
cp README.md media/fonts/LICENSE-DejaVu.txt dist/BVB/
tar -C dist -czf "dist/BVB-${version}-steam-linux.tar.gz" BVB
echo "Built dist/BVB/ and dist/BVB-${version}-steam-linux.tar.gz"
