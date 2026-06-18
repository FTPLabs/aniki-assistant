---
name: code-quality-check
description: Detect and fix indentation errors, extra spaces, duplicate code blocks, repeated logic, and incorrect/placeholder values in Python and TypeScript files. Use when the user asks to check code quality, find duplicates, fix indentation, clean up whitespace, or audit for bad values.
---

# Code Quality Check Skill

Systematically find and fix 5 categories of code quality issues: indentation, spaces, duplicates, repetitions, and incorrect values.

## When to Use

- User says "check code quality", "find duplicates", "fix indentation", "clean up whitespace"
- Before committing or releasing code
- After merging branches or large refactors
- Periodic codebase audits

## Step-by-Step Process

### 1. Indentation Check

**What to look for:**
- Mixed tabs and spaces in the same file
- Inconsistent indentation level (e.g., 2 spaces in a 4-space project)
- Over-indented or under-indented blocks
- Trailing whitespace on lines

**How to detect (Python):**
```bash
# Find files with mixed tabs/spaces
grep -rPn "\t" --include="*.py" .

# Find trailing whitespace
grep -rPn " +$" --include="*.py" .

# Check with pycodestyle
pip install pycodestyle
pycodestyle --statistics --count src/
```

**How to detect (TypeScript/JS):**
```bash
# Find mixed indentation
grep -rPn "\t" --include="*.ts" --include="*.tsx" src/

# Use ESLint
npx eslint --rule '{"indent": ["error", 2]}' src/
```

**Fix:**
- Python: use `autopep8 --in-place --recursive .` or `black .`
- TS/JS: use `prettier --write "src/**/*.{ts,tsx}"`

---

### 2. Extra Spaces Check

**What to look for:**
- Double spaces inside code (not in strings)
- Trailing spaces at end of lines
- Extra blank lines (more than 2 consecutive)
- Spaces before colons/commas where not needed
- Multiple spaces in import statements

**How to detect:**
```bash
# Trailing spaces
grep -rPn " +$" --include="*.py" --include="*.ts" .

# Double spaces (Python)
grep -rPn "  +" --include="*.py" . | grep -v "^.*#" | grep -v "^\s"

# Extra blank lines (3+ in a row)
grep -Pzn "\n\n\n" --include="*.py" -r .
```

**Fix (Python):**
```python
import re
content = open(file).read()
# Remove trailing whitespace
content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
# Max 2 consecutive blank lines
content = re.sub(r'\n{3,}', '\n\n', content)
open(file, 'w').write(content)
```

---

### 3. Duplicate Code Detection

**What to look for:**
- Copy-pasted functions with same logic
- Identical import blocks in multiple files
- Repeated constant definitions
- Same error handling patterns copy-pasted

**How to detect:**
```bash
# Install duplicate detector
pip install pylint
pylint --disable=all --enable=duplicate-code src/

# For JS/TS
npx jsinspect src/

# Quick manual check — find identical function bodies
grep -rn "def " --include="*.py" . | sort | uniq -d
```

**Manual Detection Pattern:**
1. `grep` for repeated function signatures
2. Compare files with `diff file1.py file2.py`
3. Look for copy-paste blocks longer than 10 lines

**Fix:** Extract to shared utility function/module.

---

### 4. Repetition Check (Logic & String Repetition)

**What to look for:**
- Same string literal used 3+ times (should be a constant)
- Same expression computed multiple times in a function
- Repeated conditional logic that could be a helper
- Repeated `try/except` blocks with identical bodies

**How to detect:**
```bash
# Find repeated string literals (Python)
grep -roh '"[^"]\{5,\}"' --include="*.py" . | sort | uniq -c | sort -rn | head -20

# Find repeated function calls
grep -rn "\.format\|f\"" --include="*.py" . | sort | uniq -c | sort -rn | head -20
```

**Examples of bad patterns:**
```python
# BAD — same string 3 times
if error_type == "connection_error":
    logger.error("Connection failed: retry")
elif error_type == "timeout_error":
    logger.error("Connection failed: retry")   # duplicate!
elif error_type == "auth_error":
    logger.error("Connection failed: retry")   # duplicate!

# GOOD
RETRY_MSG = "Connection failed: retry"
logger.error(RETRY_MSG)
```

**Fix:** Extract repeated strings to constants at top of file or shared constants module.

---

### 5. Incorrect / Placeholder Values Check

**What to look for:**
- TODO / FIXME / HACK / XXX comments left in production code
- Placeholder values: `"your_api_key"`, `"example.com"`, `"change_me"`, `"TODO"`
- Hardcoded test data: `"test@test.com"`, `"password123"`, `"localhost:3000"`
- Magic numbers without explanation (0, 1, -1 are fine; 47, 128, 86400 need a constant)
- `None` returns where proper error handling is needed
- Debug flags accidentally left `True`

**How to detect:**
```bash
# Find TODO/FIXME
grep -rn "TODO\|FIXME\|HACK\|XXX\|TEMP\|NOCOMMIT" --include="*.py" --include="*.ts" .

# Find placeholder values
grep -rniP "(your_api_key|change.?me|example\.com|test@test|password123|hardcoded|placeholder)" \
  --include="*.py" --include="*.ts" .

# Find debug flags
grep -rn "DEBUG\s*=\s*True\|debug\s*=\s*true" --include="*.py" --include="*.ts" .

# Find magic numbers (non-obvious)
grep -rPn "\b(86400|3600|1024|255|65535|9999|99999)\b" --include="*.py" . | grep -v "^\s*#"
```

**Fix:**
- Move to constants: `MAX_RETRIES = 3`
- Move sensitive config to `.env` / environment variables
- Replace placeholders with proper values or raise `NotImplementedError`

---

## Full Audit Command Sequence

Run this for a complete check on any Python project:

```bash
#!/bin/bash
echo "=== 1. Indentation ==="
grep -rPn "\t" --include="*.py" . | head -20

echo "=== 2. Trailing Spaces ==="
grep -rPn " +$" --include="*.py" . | head -20

echo "=== 3. Extra Blank Lines ==="
grep -Pzn "(\n){3,}" --include="*.py" -rl . | head -10

echo "=== 4. TODO/FIXME ==="
grep -rn "TODO\|FIXME\|HACK\|XXX" --include="*.py" .

echo "=== 5. Placeholder Values ==="
grep -rniP "(your_api_key|change.me|example\.com|test@test|password123)" --include="*.py" .

echo "=== 6. Debug Flags ==="
grep -rn "DEBUG\s*=\s*True" --include="*.py" .

echo "=== Done! ==="
```

## Output Format

When reporting issues, use this format:

```
## Code Quality Report

### ❌ Indentation Issues (N found)
- `src/core/engine.py:42` — mixed tabs and spaces
- `src/ui/window.py:15` — 3-space indent in 4-space file

### ❌ Extra Spaces (N found)  
- `src/main.py:7` — trailing whitespace
- `src/core/memory.py:23,24,25` — 3 consecutive blank lines

### ❌ Duplicate Code (N found)
- `src/core/tts.py:45-67` duplicates `src/core/speech.py:89-111`

### ❌ Repeated Values (N found)
- `"connection timeout"` repeated 4 times — extract to constant

### ❌ Incorrect/Placeholder Values (N found)
- `src/config.py:12` — `API_KEY = "your_api_key_here"` placeholder
- `src/main.py:5` — `DEBUG = True` left enabled

### ✅ Summary
N issues found. Estimated fix time: X minutes.
```
