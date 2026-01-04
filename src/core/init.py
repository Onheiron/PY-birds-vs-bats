#!/usr/bin/env python3
"""
Configuration initialization module for BVB game.
Loads and validates YAML configuration, applying values to game globals.
"""
import sys
import os
import argparse
import random

try:
    import yaml
except Exception:
    yaml = None

try:
    import jsonschema
except Exception:
    jsonschema = None


def load_config_file(path):
    """Load and validate YAML configuration file."""
    cfg = {}
    if not path:
        return cfg
    if yaml is None:
        try:
            print(f"Warning: PyYAML not installed; cannot load config from {path}", file=sys.stderr)
        except Exception:
            pass
        return cfg
    try:
        with open(path, 'r') as fh:
            data = yaml.safe_load(fh)
            if isinstance(data, dict):
                cfg = data
    except Exception as e:
        try:
            print(f"Failed to load config {path}: {e}", file=sys.stderr)
        except Exception:
            pass
    
    # Validate config against schema if jsonschema is available
    if cfg and jsonschema is not None:
        schema_path = os.path.join(os.path.dirname(__file__), 'config.schema.json')
        if os.path.exists(schema_path):
            try:
                import json
                with open(schema_path, 'r') as schema_file:
                    schema = json.load(schema_file)
                jsonschema.validate(instance=cfg, schema=schema)
                try:
                    print(f"Config validation: OK", file=sys.stderr)
                except Exception:
                    pass
            except jsonschema.ValidationError as ve:
                try:
                    print(f"Config validation error: {ve.message}", file=sys.stderr)
                    print(f"At path: {' -> '.join(str(p) for p in ve.path)}", file=sys.stderr)
                    sys.exit(1)
                except Exception:
                    sys.exit(1)
            except Exception as e:
                try:
                    print(f"Warning: Could not validate config schema: {e}", file=sys.stderr)
                except Exception:
                    pass
    
    return cfg


def init_config():
    """
    Initialize game configuration from YAML file.
    Parses command-line arguments and loads configuration.
    Default config file is 'config.yml' if --config is not specified.
    Default theme file is 'theme.yml' if --theme is not specified.

    Returns:
        tuple: (config_dict, args_namespace) - The loaded config and parsed CLI args
    """
    # Parse CLI args (only config/theme paths here; allow other args to pass through)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', default='config.yml', help='Path to YAML config file (default: config.yml)')
    parser.add_argument('--theme', default='theme.yml', help='Path to theme YAML file (default: theme.yml)')
    args, _rest = parser.parse_known_args()

    config_path = args.config if args and args.config else 'config.yml'
    _config = load_config_file(config_path)

    # Config is now required
    if not _config:
        try:
            print(f"ERROR: Configuration file '{config_path}' not found or invalid.", file=sys.stderr)
            print(f"Please ensure config.yml exists or specify a valid config with --config", file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)

    # Set theme path for theme module to use
    theme_path = args.theme if args and args.theme else 'theme.yml'
    os.environ['BVB_THEME_PATH'] = theme_path

    return _config, args


def apply_config_to_namespace(namespace, config_dict, path=""):
    """
    Recursively populate a SimpleNamespace from configuration dict.
    Creates attributes if they don't exist.
    Handles dicts with non-string keys by keeping them as dicts.
    
    Args:
        namespace: SimpleNamespace object to populate
        config_dict: Dictionary with configuration values
        path: Current path for debugging (internal use)
    """
    from types import SimpleNamespace
    
    if not isinstance(config_dict, dict):
        return
    
    for key, value in config_dict.items():
        # Skip non-string keys (will be handled as regular dicts)
        if not isinstance(key, str):
            continue
            
        # If the value is a dict, check if all keys are strings
        if isinstance(value, dict):
            # If dict has non-string keys, keep it as a dict
            if any(not isinstance(k, str) for k in value.keys()):
                setattr(namespace, key, value)
            else:
                # Create nested SimpleNamespace for string-keyed dicts
                if not hasattr(namespace, key):
                    setattr(namespace, key, SimpleNamespace())
                nested_ns = getattr(namespace, key)
                apply_config_to_namespace(nested_ns, value, f"{path}.{key}" if path else key)
        else:
            # Direct assignment
            setattr(namespace, key, value)


def dict_to_namespace(config_dict):
    """
    Convert a nested dict to nested SimpleNamespace objects.
    
    Args:
        config_dict: Dictionary to convert
        
    Returns:
        SimpleNamespace with nested structure
    """
    from types import SimpleNamespace
    
    ns = SimpleNamespace()
    apply_config_to_namespace(ns, config_dict)
    return ns
