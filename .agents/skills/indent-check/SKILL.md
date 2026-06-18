---
name: indent-check
description: Detect and fix indentation errors in Python and TypeScript files. Finds mixed tabs/spaces, wrong indent widths, over/under-indented blocks. Use when user says "fix indentation", "check tabs", "indent error", or before committing code.
---

# Indentation Check Skill

Detect and fix all indentation issues in Python and TypeScript/JavaScript files.

## What This Skill Detects

1. **Mixed tabs and spaces** — Fatal in Python, ugly everywhere
2. **Wrong indent width** — 3 spaces in a 4-space project, etc.
3. **Over-indented blocks** — Extra level of indentation
4. **Under-indented blocks** — Missing level after `if`/`def`/`class`
5. **Trailing whitespace** — Spaces/tabs at end of lines

## Detection Commands

### Python — Find All Issues
```bash
# Mixed tabs and spaces (Python fatal)
grep -rPn "^\t" --include="*.py" .

# Trailing whitespace
grep -rPn "[ \t]+$" --include="*.py" .

# Lines with inconsistent indent (e.g., 3 spaces in 4-space project)
python3 -c "
import ast, sys
for f in __import__('glob').glob('**/*.py', recursive=True):
    try:
        ast.parse(open(f).read())
    except IndentationError as e:
        print(f'{f}:{e.lineno}: {e.msg}')
"
```

### TypeScript/JavaScript
```bash
# Find tabs (if project uses spaces)
grep -rPn "^\t" --include="*.ts" --include="*.tsx" --include="*.js" src/

# Trailing whitespace
grep -rPn "[ \t]+$" --include="*.ts" --include="*.tsx" src/
```

## Auto-Fix Commands

### Python — Fix with black (recommended)
```bash
pip install black
black .
```

### Python — Fix with autopep8 (less aggressive)
```bash
pip install autopep8
autopep8 --in-place --recursive --select=E1,W1,W2,W3 .
```

### TypeScript — Fix with prettier
```bash
npx prettier --write "src/**/*.{ts,tsx,js,jsx}"
```

### Remove trailing whitespace (all files)
```bash
# Linux/Mac
find . -name "*.py" -o -name "*.ts" | xargs sed -i 's/[[:space:]]*$//'

# Python script (cross-platform)
python3 -c "
import glob, re
for f in glob.glob('**/*.py', recursive=True) + glob.glob('src/**/*.ts', recursive=True):
    content = open(f, encoding='utf-8', errors='ignore').read()
    fixed = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
    if fixed != content:
        open(f, 'w', encoding='utf-8').write(fixed)
        print(f'Fixed: {f}')
"
```

## Output Format

```
## Indentation Issues

- `src/core/engine.py:42` — TAB found (project uses spaces)
- `src/ui/window.py:15` — trailing whitespace (12 chars)
- `src/main.py:88` — IndentationError: unexpected indent

Total: N files affected
Fix: run `black .` or `prettier --write src/`
```
