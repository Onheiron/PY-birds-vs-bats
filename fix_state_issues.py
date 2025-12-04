#!/usr/bin/env python3
"""
Fix issues with state. prefix in function definitions, global statements, and keyword argument names.
"""

import re

def fix_file(filepath):
    """Fix incorrect state. prefixes in specific contexts."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Fix: function parameter definitions (e.g., `def foo(state.level):` -> `def foo(level):`)
    content = re.sub(r'def\s+\w+\s*\([^)]*state\.(\w+)', lambda m: m.group(0).replace('state.' + m.group(1), m.group(1)), content)
    
    # Fix: global statements (e.g., `global state.score` -> nothing, remove global statements entirely)
    content = re.sub(r'^\s*global\s+state\.\w+.*$', '', content, flags=re.MULTILINE)
    
    # Fix: keyword argument names in function calls
    # Pattern: keyword_name=value where keyword_name starts with state.
    # e.g., `foo(state.score=5)` -> `foo(score=5)`
    content = re.sub(r'(\w+\s*\([^)]*)\bstate\.(\w+)\s*=', r'\1\2=', content)
    
    # Fix: string literals that got changed (e.g., 'state.score' should be 'score')
    # This is tricky - we need to fix cases like ach.check_achievements_event('state.score', ...)
    content = re.sub(r"'state\.(\w+)'", r"'\1'", content)
    content = re.sub(r'"state\.(\w+)"', r'"\1"', content)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Fixed issues in {filepath}")

if __name__ == '__main__':
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else '/Users/carlomoretti/Developer/Projects/BVB/start_new.py'
    fix_file(filepath)
