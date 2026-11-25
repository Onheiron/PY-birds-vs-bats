"""What's new: the sections of CHANGELOG.md, one per version (shown on the title screen)."""

from src.core import paths


def sections(text):
    """{version: [lines]} of a changelog: '## <version>' headings, '- ' lines under them."""
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith('## '):
            current = line[3:].strip().lstrip('vV')
            out[current] = []
        elif current and line.strip().startswith('- '):
            out[current].append(line.strip()[2:].strip())
    return out


def notes(version):
    """The changelog lines of ``version`` (empty when there are none)."""
    path = paths.find('CHANGELOG.md')
    if not path:
        return []
    try:
        with open(path, encoding='utf-8') as f:
            return sections(f.read()).get(str(version).lstrip('vV'), [])
    except OSError:
        return []
