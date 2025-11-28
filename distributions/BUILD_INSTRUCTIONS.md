# Build Instructions

## macOS (Current)

Already built! You have:
- `dist/BVB` - The executable
- `dist/Launch BVB.app` - Double-click launcher with proper terminal size

## Linux

You need to build on a Linux machine:

```bash
# On Linux system
pip install pyinstaller
pyinstaller --onefile --name BVB --console start.py

# The executable will be in dist/BVB
# Users can run it with: ./BVB
```

### Using Docker (from macOS)

```bash
# Build Linux executable using Docker
docker run --rm -v "$(pwd):/src" python:3.11-slim bash -c "
  cd /src && \
  pip install pyinstaller && \
  pyinstaller --onefile --name BVB-linux --console start.py
"

# The Linux executable will be in dist/BVB-linux
```

### Create Linux .desktop launcher

After building on Linux, create this file:

**BVB.desktop**:
```ini
[Desktop Entry]
Name=BVB
Comment=Bird vs Bat Juggling Game
Exec=/path/to/BVB
Terminal=true
Type=Application
Categories=Game;
```

Save it in `~/.local/share/applications/` or next to the executable.

## Windows

You need to build on a Windows machine:

```bash
# On Windows with Python installed
pip install pyinstaller
pyinstaller --onefile --name BVB --console start.py

# The executable will be in dist\BVB.exe
# Users can double-click BVB.exe to play
```

### Using Wine (experimental, from macOS/Linux)

```bash
# Install wine and python via wine
# Then:
wine python -m pip install pyinstaller
wine python -m PyInstaller --onefile --name BVB --console start.py
```

## Distribution

Each platform needs its own build:
- **macOS**: Distribute `Launch BVB.app` or `BVB`
- **Linux**: Distribute `BVB` with execute permissions
- **Windows**: Distribute `BVB.exe`

All executables are standalone - no Python installation required!
