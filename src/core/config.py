"""Configuration loading: CLI options, YAML files, merging and validation.

The bundled ``config.yml`` holds every tunable. A file passed with ``--config``
only needs the values it changes: it is merged over the defaults, exactly like
the difficulty presets (``config_easy.yml``, ``config_hard.yml``, ...).
"""

import argparse
import json
import os
import sys
from types import SimpleNamespace

from src.core import paths

try:
    import yaml
except ImportError:
    yaml = None

try:
    import jsonschema
except ImportError:
    jsonschema = None

DEFAULT_CONFIG = 'config.yml'
DEFAULT_THEME = 'theme.yml'
SCHEMA_FILE = 'config.schema.json'


class ConfigError(Exception):
    """A configuration file is missing, unreadable or invalid."""


def parse_args(argv=None):
    """Parse the command line (unknown options are left for others to handle)."""
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    parser.add_argument('--theme', default=DEFAULT_THEME)
    args, _rest = parser.parse_known_args(argv)
    return args


def load_yaml(path):
    """Load a YAML mapping from ``path``."""
    if yaml is None:
        raise ConfigError("PyYAML is not installed (pip install pyyaml)")
    try:
        with open(path, encoding='utf-8') as handle:
            data = yaml.safe_load(handle)
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping of sections")
    return data


def deep_merge(base, override):
    """Return ``base`` with ``override`` merged in; override values win."""
    result = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def validate(config, source='configuration'):
    """Check ``config`` against the JSON schema (skipped without jsonschema)."""
    schema_path = paths.find(SCHEMA_FILE)
    if jsonschema is None or schema_path is None:
        return
    with open(schema_path, encoding='utf-8') as handle:
        schema = json.load(handle)
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(config), key=lambda e: list(map(str, e.path)))
    if errors:
        details = '\n'.join(
            f"  {' -> '.join(str(p) for p in e.path) or '(top level)'}: {e.message}" for e in errors[:10]
        )
        raise ConfigError(f"{source} is invalid:\n{details}")


def load_config(name=DEFAULT_CONFIG):
    """Load a configuration: the bundled defaults with ``name`` merged on top."""
    default_path = paths.bundled(DEFAULT_CONFIG)
    path = paths.find(name)
    if path is None:
        raise ConfigError(f"configuration file '{name}' not found")

    config = load_yaml(path)
    if os.path.isfile(default_path) and not os.path.samefile(path, default_path):
        config = deep_merge(load_yaml(default_path), config)
    if not config:
        raise ConfigError(f"configuration file '{name}' is empty")

    validate(config, source=name)
    return config


def init_config(argv=None):
    """Load the configuration selected on the command line.

    Returns (config_dict, args). Exits with a readable message when the
    configuration cannot be used.
    """
    args = parse_args(argv)
    try:
        config = load_config(args.config or DEFAULT_CONFIG)
    except ConfigError as error:
        sys.exit(f"ERROR: {error}")

    # The theme module picks its file up from the environment
    os.environ['BVB_THEME_PATH'] = args.theme or DEFAULT_THEME
    return config, args


def apply_to_namespace(namespace, config_dict):
    """Recursively copy a config mapping onto a SimpleNamespace.

    Nested mappings become nested namespaces, except those with non-string
    keys (tier tables such as ``{1: 24, 2: 48}``), which stay plain dicts.
    """
    if not isinstance(config_dict, dict):
        return
    for key, value in config_dict.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, dict) and all(isinstance(k, str) for k in value):
            nested = getattr(namespace, key, None)
            if not isinstance(nested, SimpleNamespace):
                nested = SimpleNamespace()
                setattr(namespace, key, nested)
            apply_to_namespace(nested, value)
        else:
            setattr(namespace, key, value)


def to_namespace(config_dict):
    """Convert a nested mapping to nested SimpleNamespace objects."""
    namespace = SimpleNamespace()
    apply_to_namespace(namespace, config_dict)
    return namespace


def reset_namespace(namespace, config_dict):
    """Replace the contents of ``namespace`` in place (references stay valid)."""
    for attr in list(vars(namespace)):
        delattr(namespace, attr)
    apply_to_namespace(namespace, config_dict)
