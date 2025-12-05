#!/usr/bin/env python3
"""
Script to remove all non-essential try/catch blocks from start_new.py.
Keeps only:
- Import blocks for optional modules (yaml, jsonschema, firebase_client)
- Terminal setup/cleanup (setup, cleanup, get_key functions)
- Background thread safety wrappers (_safe_call, background_call)
- Final exception handler in main try block
"""
import re

# Read the file
with open('start_new.py', 'r') as f:
    content = f.read()

# Essential try/catch patterns to keep (line numbers are approximate)
essential_patterns = [
    # Import blocks
    (r'try:\s+import yaml\s+except Exception:\s+yaml = None', True),
    (r'try:\s+import jsonschema\s+except Exception:\s+jsonschema = None', True),
    (r'try:\s+import firebase_client\s+except Exception:\s+firebase_client = None', True),
    
    # Background call safety
    (r'def _safe_call\(func,.*?\):\s+try:.*?except Exception:\s+pass', True),
    (r'def background_call\(func,.*?\):.*?try:.*?except Exception:\s+pass', True),
    
    # Terminal setup/cleanup
    (r'def cleanup\(\):.*?try:.*?except.*?pass.*?finally:', True),
    (r'def setup\(\):.*', True),
    (r'def get_key\(\):.*?try:.*?except Exception:.*?return None', True),
    
    # Main game loop exception handler
    (r'except KeyboardInterrupt:\s+pass', True),
    (r'except Exception:.*?finally:\s+cleanup\(\)', True),
]

# This is a complex transformation. Instead of regex, we'll do a simpler approach:
# Remove all try/except blocks except those in specific functions

functions_to_preserve = [
    '_safe_call',
    'background_call', 
    'cleanup',
    'setup',
    'get_key',
]

# Split into lines for line-by-line processing
lines = content.split('\n')

# Track which try blocks to keep
in_preserved_function = False
current_function = None
indent_stack = []
output_lines = []
skip_until_indent = None

i = 0
while i < len(lines):
    line = lines[i]
    
    # Detect function definitions
    if line.strip().startswith('def '):
        func_match = re.match(r'\s*def\s+(\w+)\s*\(', line)
        if func_match:
            current_function = func_match.group(1)
            in_preserved_function = current_function in functions_to_preserve
    
    # Handle import try/except blocks (keep them)
    if re.match(r'\s*try:\s*$', line) and i + 1 < len(lines):
        next_line = lines[i + 1].strip()
        if next_line.startswith('import '):
            # This is an import try block - keep it
            output_lines.append(line)
            i += 1
            continue
    
    # Main logic: remove try/except in non-preserved functions
    if not in_preserved_function:
        # Remove standalone try: except: pass blocks
        if re.match(r'\s*try:\s*$', line):
            # Found a try block - need to remove it and its except
            try_indent = len(line) - len(line.lstrip())
            
            # Skip the try line
            i += 1
            if i >= len(lines):
                break
                
            # Collect and output the try block content (unindent by 4)
            while i < len(lines):
                inner_line = lines[i]
                inner_indent = len(inner_line) - len(inner_line.lstrip())
                
                # If we hit the except clause
                if re.match(r'\s*except\s', inner_line) and inner_indent == try_indent:
                    # Skip the except block
                    i += 1
                    while i < len(lines):
                        except_line = lines[i]
                        except_indent = len(except_line) - len(except_line.lstrip())
                        if except_indent <= try_indent and except_line.strip():
                            break
                        i += 1
                    break
                
                # If indentation decreased back to try level, we're done
                if inner_indent <= try_indent and inner_line.strip():
                    break
                
                # Output the line with reduced indentation
                if inner_line.strip():
                    output_lines.append(inner_line[4:] if len(inner_line) > 4 else inner_line)
                else:
                    output_lines.append(inner_line)
                i += 1
            continue
    
    output_lines.append(line)
    i += 1

# Write the output
with open('start_new.py', 'w') as f:
    f.write('\n'.join(output_lines))

print("Try/catch blocks removed successfully!")
