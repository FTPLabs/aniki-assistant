---
name: value-auditor
description: Audit code for placeholder values, TODO/FIXME comments, hardcoded secrets, debug flags, magic numbers, and incorrect default values. Use when user says "check for bad values", "find placeholders", "find TODOs", "hardcoded values", "debug flags", or before any production release.
---

# Value Auditor Skill

Scan codebase for incorrect, placeholder, debug, or dangerous values that must be fixed before production.

## What This Skill Detects

1. **TODO/FIXME/HACK comments** — unfinished work
2. **Placeholder strings** — `"your_api_key"`, `"change_me"`, `"example.com"`
3. **Hardcoded secrets** — API keys, passwords, tokens in source code
4. **Debug flags** — `DEBUG = True`, `VERBOSE = True` left on
5. **Magic numbers** — unexplained numeric constants
6. **None/null returns** — where proper error handling is needed
7. **Test data in production code** — `"test@test.com"`, `"password123"`
8. **Localhost hardcodes** — `"localhost:3000"`, `"127.0.0.1"` in prod code

## Detection Commands

### TODO/FIXME Scan
```bash
echo "=== TODO/FIXME/HACK ==="
grep -rn "TODO\|FIXME\|HACK\|XXX\|NOCOMMIT\|TEMP:\|@deprecated" \
  --include="*.py" --include="*.ts" --include="*.tsx" \
  --exclude-dir=node_modules --exclude-dir=.git .
```

### Placeholder Values
```bash
echo "=== Placeholder/Default Values ==="
grep -rniP \
  "(your[_-]api[_-]key|change[_-]?me|example\.com|placeholder|your[_-]token|insert[_-]here|put[_-]your|replace[_-]this|dummy[_-]value|test@test|foo@bar)" \
  --include="*.py" --include="*.ts" --include="*.env*" \
  --exclude-dir=node_modules .
```

### Debug Flags
```bash
echo "=== Debug Flags ==="
grep -rniP \
  "(DEBUG\s*=\s*True|debug\s*=\s*true|VERBOSE\s*=\s*True|verbose\s*=\s*true|LOG_LEVEL\s*=\s*['\"]debug['\"])" \
  --include="*.py" --include="*.ts" --include="*.env" .
```

### Potential Hardcoded Secrets
```bash
echo "=== Potential Hardcoded Secrets ==="
grep -rniP \
  "(api[_-]?key\s*=\s*['\"][A-Za-z0-9]{16,}|secret\s*=\s*['\"][^'\"]{8,}|password\s*=\s*['\"][^'\"]{4,}|token\s*=\s*['\"][A-Za-z0-9]{20,})" \
  --include="*.py" --include="*.ts" \
  --exclude-dir=node_modules --exclude-dir=.git . | grep -v "os\.environ\|process\.env\|getenv\|#"
```

### Hardcoded URLs/IPs
```bash
echo "=== Hardcoded Localhost/IPs ==="
grep -rniP \
  "(localhost:\d+|127\.0\.0\.1:\d+|0\.0\.0\.0:\d+)" \
  --include="*.py" --include="*.ts" \
  --exclude-dir=node_modules . | grep -v "^\s*#\|^\s*//"
```

### Magic Numbers
```bash
echo "=== Magic Numbers (should be named constants) ==="
# Numbers > 10 that appear in logic (not in lists/arrays)
grep -rPn "\b(86400|3600|1440|604800|1000000|65535|32767|8080|5000|9999)\b" \
  --include="*.py" --include="*.ts" . | grep -v "^\s*#\|^\s*//"
```

### None/null Returns (Python)
```bash
echo "=== Silent None Returns ==="
# Functions that return None without logging on error paths
grep -rPn "^\s+return None" --include="*.py" . | grep -v "^\s*#"
```

## Full Audit Script

Run before any release:

```bash
#!/bin/bash
set -e
PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    echo ""
    echo "▶ Checking: $name"
    result=$(eval "$cmd" 2>/dev/null)
    if [ -n "$result" ]; then
        echo "  ❌ Issues found:"
        echo "$result" | head -10 | sed 's/^/    /'
        FAIL=$((FAIL + 1))
    else
        echo "  ✅ Clean"
        PASS=$((PASS + 1))
    fi
}

check "TODO/FIXME comments" \
  "grep -rn 'TODO\|FIXME\|HACK\|XXX' --include='*.py' --include='*.ts' . 2>/dev/null"

check "Placeholder values" \
  "grep -rniP '(your_api_key|change.me|example\.com|placeholder)' --include='*.py' --include='*.ts' . 2>/dev/null"

check "Debug flags enabled" \
  "grep -rniP '(DEBUG\s*=\s*True|debug\s*=\s*true)' --include='*.py' --include='*.ts' . 2>/dev/null"

check "Hardcoded passwords" \
  "grep -rniP 'password\s*=\s*[\"'\''][^\"'\'']{4,}' --include='*.py' . 2>/dev/null | grep -v 'os\.environ\|getenv'"

check "Hardcoded localhost URLs" \
  "grep -rniP 'localhost:\d{4}' --include='*.py' --include='*.ts' . 2>/dev/null | grep -v '#'"

echo ""
echo "================================"
echo "Results: ✅ $PASS passed | ❌ $FAIL issues"
echo "================================"
[ $FAIL -eq 0 ] && exit 0 || exit 1
```

## Pre-Release Checklist

Before tagging a release, verify:

- [ ] `grep -r "TODO\|FIXME" --include="*.py" .` returns nothing
- [ ] No `DEBUG = True` in any file
- [ ] All API keys come from env vars, not hardcoded
- [ ] No `"localhost"` in production URLs (use env vars)
- [ ] No test credentials (`test@test.com`, `password123`)
- [ ] No placeholder strings (`"your_key_here"`, `"change_me"`)

## Output Format

```
## Value Audit Report

### ❌ TODO/FIXME (3 found — must fix before release)
- `src/core/tts.py:45` — # TODO: add Silero v5 support
- `src/ui/chat_window.py:200` — # FIXME: streaming tokens flicker

### ❌ Debug Flags (1 found — DANGEROUS)
- `src/main.py:12` — DEBUG = True

### ⚠️ Hardcoded URLs (2 found — use env vars)
- `src/core/ai_engine.py:8` — OLLAMA_BASE_URL = "http://localhost:11434"

### ✅ No placeholder values
### ✅ No hardcoded secrets

Priority: Fix DEBUG flag immediately. TODOs before v1.0 release.
```
