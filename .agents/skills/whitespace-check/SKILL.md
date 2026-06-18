---
name: whitespace-check
description: Detect extra spaces, double spaces, trailing whitespace, and excessive blank lines in code files. Use when user says "clean up whitespace", "extra spaces", "blank lines", "trailing spaces", or "whitespace issues".
---

# Whitespace Check Skill

Find and fix all whitespace problems: trailing spaces, double spaces inside code, excessive blank lines, and spacing inconsistencies.

## What This Skill Detects

1. **Trailing whitespace** — spaces/tabs at end of lines
2. **Double spaces in code** — `x  =  5` instead of `x = 5`
3. **Excessive blank lines** — 3+ consecutive empty lines
4. **Space before colon** — `def func () :` instead of `def func():`
5. **Missing space after comma** — `f(a,b,c)` instead of `f(a, b, c)`
6. **Multiple spaces in imports** — `import  os` 

## Detection Commands

```bash
# 1. Trailing whitespace
echo "=== Trailing whitespace ===" 
grep -rPn "[ \t]+$" --include="*.py" --include="*.ts" . | head -30

# 2. Double spaces in non-string code (Python)
echo "=== Double spaces ==="
grep -rPn "(?<!['\"])  +(?!['\"])" --include="*.py" . | grep -v "^\s*#" | head -20

# 3. Excessive blank lines (3+ in a row)
echo "=== Excessive blank lines ==="
grep -rPzln "(\n[ \t]*){3,}" --include="*.py" . | head -10

# 4. Space before colon in Python
echo "=== Space before colon ==="
grep -rPn "\s+:" --include="*.py" . | grep -E "def |class |if |for |while " | head -20

# 5. Missing space after comma
echo "=== Missing space after comma ==="
grep -rPn ",[^ \n\)]" --include="*.py" . | grep -v "^\s*#" | grep -v "\"" | head -20
```

## Auto-Fix

### Python — all whitespace issues
```bash
pip install autopep8
autopep8 --in-place --recursive --select=E2,W2,W3 .
# Or use black for opinionated formatting:
pip install black && black .
```

### TypeScript — all whitespace issues  
```bash
npx prettier --write "src/**/*.{ts,tsx}"
```

### Manual fix script (Python, cross-platform)
```python
import re, glob

for filepath in glob.glob('**/*.py', recursive=True):
    try:
        content = open(filepath, encoding='utf-8').read()
        # Remove trailing whitespace
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
        # Reduce 3+ blank lines to 2
        content = re.sub(r'\n{3,}', '\n\n', content)
        open(filepath, 'w', encoding='utf-8').write(content)
    except Exception as e:
        print(f"Skip {filepath}: {e}")
```

## Output Format

```
## Whitespace Issues

### Trailing Whitespace (N lines)
- `src/main.py:7,12,34` — trailing spaces

### Excessive Blank Lines (N locations)  
- `src/core/memory.py:55-58` — 4 consecutive blank lines (max 2)

### Double Spaces (N locations)
- `src/commands.py:23` — `result  =  handler(match)`

Total: N files need cleanup
Fix: `black .` (Python) or `prettier --write src/` (TS)
```
