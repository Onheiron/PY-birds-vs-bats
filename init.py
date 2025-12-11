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
    
    Returns:
        tuple: (config_dict, args_namespace) - The loaded config and parsed CLI args
    """
    # Parse CLI args (only config path here; allow other args to pass through)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', help='Path to YAML config file to override defaults')
    args, _rest = parser.parse_known_args()
    _config = load_config_file(args.config if args and args.config else None)
    
    return _config, args


def apply_config_to_namespace(namespace, config_dict, path=""):
    """
    Recursively apply configuration values from a dict to a SimpleNamespace.
    
    Args:
        namespace: SimpleNamespace object to update
        config_dict: Dictionary with configuration values
        path: Current path for debugging (internal use)
    """
    from types import SimpleNamespace
    
    if not isinstance(config_dict, dict):
        return
    
    for key, value in config_dict.items():
        if not hasattr(namespace, key):
            # Skip keys that don't exist in the namespace
            try:
                print(f"Warning: Config key '{path}.{key}' not found in constants", file=sys.stderr)
            except Exception:
                pass
            continue
        
        current_value = getattr(namespace, key)
        
        # If the current value is a SimpleNamespace and the config value is a dict,
        # recurse into it
        if isinstance(current_value, SimpleNamespace) and isinstance(value, dict):
            apply_config_to_namespace(current_value, value, f"{path}.{key}" if path else key)
        else:
            # Direct assignment - preserve the type if possible
            try:
                if isinstance(current_value, type(value)):
                    setattr(namespace, key, value)
                elif isinstance(current_value, (int, float)) and isinstance(value, (int, float)):
                    # Allow int/float conversion
                    setattr(namespace, key, type(current_value)(value))
                else:
                    setattr(namespace, key, value)
            except Exception as e:
                try:
                    print(f"Warning: Failed to set '{path}.{key}': {e}", file=sys.stderr)
                except Exception:
                    pass
