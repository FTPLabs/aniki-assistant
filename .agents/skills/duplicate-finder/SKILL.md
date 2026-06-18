---
name: duplicate-finder
description: Find duplicate code blocks, copy-pasted functions, repeated constants, and identical logic patterns in Python and TypeScript projects. Use when user says "find duplicates", "duplicate code", "copy-paste", "DRY principle", or "repeated logic".
---

# Duplicate Code Finder Skill

Identify copy-pasted code, duplicate functions, repeated string literals, and identical logic blocks that should be extracted into shared utilities.

## What This Skill Detects

1. **Duplicate function bodies** — same logic under different names
2. **Copy-pasted code blocks** — 5+ identical lines in multiple places
3. **Repeated string literals** — same string used 3+ times (needs a constant)
4. **Repeated imports** — same import in many files (needs shared re-export)
5. **Identical error handlers** — same try/except pattern everywhere
6. **Repeated API call patterns** — same fetch/request boilerplate

## Detection Commands

### Find Repeated String Literals (Python)
```bash
# Find strings repeated 3+ times
grep -roh '"[^"]\{8,\}"' --include="*.py" . | sort | uniq -c | sort -rn | awk '$1 >= 3' | head -20

# Same for single quotes
grep -roh "'[^']\{8,\}'" --include="*.py" . | sort | uniq -c | sort -rn | awk '$1 >= 3' | head -20
```

### Find Duplicate Function Signatures
```bash
# Functions with identical names (likely accidental redefine)
grep -rhn "^def \|^    def " --include="*.py" . | sort | uniq -d

# TypeScript functions
grep -rhn "^function \|^  function \|^export function \|^  async function " --include="*.ts" . | sort | uniq -d
```

### Find Copy-Pasted Blocks (manual approach)
```bash
# Find 5+ identical consecutive lines anywhere
python3 - <<'EOF'
import glob, hashlib
from collections import defaultdict

# Read all files and hash every 5-line window
hashes = defaultdict(list)
for f in glob.glob('**/*.py', recursive=True):
    lines = open(f, errors='ignore').readlines()
    for i in range(len(lines) - 4):
        block = ''.join(lines[i:i+5]).strip()
        if len(block) > 50:  # ignore tiny blocks
            h = hashlib.md5(block.encode()).hexdigest()
            hashes[h].append((f, i+1, block[:60]))

# Report duplicates
for h, locations in hashes.items():
    if len(locations) > 1:
        print(f"\nDuplicate block found in {len(locations)} places:")
        for f, line, preview in locations:
            print(f"  {f}:{line} — {preview!r}")
EOF
```

### Using pylint for duplicate detection
```bash
pip install pylint
pylint --disable=all --enable=duplicate-code --min-similarity-lines=5 src/
```

### TypeScript/JS — jsinspect
```bash
npx jsinspect --threshold 30 src/
```

## Common Duplicate Patterns to Look For

```python
# PATTERN 1: Same error message string repeated
# Bad:
logger.error("Connection failed")  # in file A
logger.error("Connection failed")  # in file B  ← duplicate
logger.error("Connection failed")  # in file C  ← duplicate

# Fix:
ERR_CONNECTION = "Connection failed"

# PATTERN 2: Same try/except wrapper
# Bad — copy-pasted in 5 functions:
try:
    result = some_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    return None

# Fix — extract to decorator or helper:
def safe_run(fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return None
```

## Fix Strategy

1. **Repeated strings** → Extract to `constants.py` or `config.py`
2. **Duplicate functions** → Move to `utils.py` or shared module
3. **Copy-pasted blocks** → Extract to a helper function
4. **Repeated imports** → Create barrel export `from .utils import *`

## Output Format

```
## Duplicate Code Report

### Repeated String Literals (extract to constants)
- `"Connection failed"` — appears 4 times in core/*.py
- `"Are you ready?"` — appears 6 times in personality.py, tts.py, reminders.py

### Duplicate Function Bodies
- `src/commands.py:open_app()` ≈ `src/utils.py:launch_app()` — 85% similar

### Copy-Pasted Blocks (5+ lines)
- `src/core/tts.py:45-52` = `src/core/speech.py:89-96` — identical error handler

Recommended actions:
1. Create `src/constants.py` for repeated strings
2. Merge `open_app`/`launch_app` into one function
3. Extract error handler to `src/utils.py`
```
