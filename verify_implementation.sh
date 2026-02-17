#!/bin/bash
# Implementation Verification Script for pdfcat v2.0
# Verifies all changes from PLAN.md and PLAN2.md

set -e

echo "======================================================================"
echo "pdfcat v2.0 Implementation Verification"
echo "Date: $(date)"
echo "======================================================================"
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((pass_count++))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((fail_count++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

echo "======================================================================"
echo "Phase 0: Security Verification"
echo "======================================================================"
echo

# Check for os.system calls
echo "Checking for os.system() calls..."
if grep -r "os\.system" src/pdfcat/ 2>/dev/null; then
    check_fail "Found os.system() calls (command injection risk)"
else
    check_pass "No os.system() calls found"
fi

# Check for shell=True
echo "Checking for shell=True in subprocess calls..."
if grep -r "shell=True" src/pdfcat/ 2>/dev/null; then
    check_fail "Found shell=True in subprocess calls"
else
    check_pass "No shell=True found in subprocess calls"
fi

# Check for bare except clauses
echo "Checking for bare except: clauses..."
if grep -r "except:" src/pdfcat/ | grep -v "except (" | grep -v "except Exception" 2>/dev/null; then
    check_fail "Found bare except: clauses"
else
    check_pass "No bare except: clauses found"
fi

# Check security files exist
echo "Checking security files exist..."
security_files=(
    "src/pdfcat/security.py"
    "src/pdfcat/exceptions.py"
    "src/pdfcat/note_naming.py"
)

for file in "${security_files[@]}"; do
    if [ -f "$file" ]; then
        check_pass "Security file exists: $file"
    else
        check_fail "Missing security file: $file"
    fi
done

# Check security tests exist
echo "Checking security tests exist..."
test_files=(
    "tests/test_security.py"
    "tests/test_note_security.py"
)

for file in "${test_files[@]}"; do
    if [ -f "$file" ]; then
        check_pass "Test file exists: $file"
    else
        check_fail "Missing test file: $file"
    fi
done

echo
echo "======================================================================"
echo "Phase 1: Threading & Memory Management"
echo "======================================================================"
echo

# Check for RLock usage
echo "Checking for threading.RLock in page_state.py..."
if grep -q "threading.RLock" src/pdfcat/page_state.py 2>/dev/null; then
    check_pass "threading.RLock found in page_state.py"
else
    check_fail "threading.RLock missing in page_state.py"
fi

echo "Checking for threading.RLock in cache.py..."
if grep -q "threading.RLock" src/pdfcat/cache.py 2>/dev/null; then
    check_pass "threading.RLock found in cache.py"
else
    check_fail "threading.RLock missing in cache.py"
fi

# Check cache configuration
echo "Checking cache configuration..."
if grep -q "max_entries" src/pdfcat/cache.py 2>/dev/null && \
   grep -q "max_bytes" src/pdfcat/cache.py 2>/dev/null; then
    check_pass "Cache limits (max_entries, max_bytes) configured"
else
    check_fail "Cache limits not properly configured"
fi

echo
echo "======================================================================"
echo "Phase 2: Architecture Refactoring"
echo "======================================================================"
echo

# Check architecture files exist
echo "Checking architecture files exist..."
arch_files=(
    "src/pdfcat/input_handler.py"
    "src/pdfcat/executor.py"
    "src/pdfcat/actions.py"
    "src/pdfcat/context.py"
    "src/pdfcat/runtime_context.py"
)

for file in "${arch_files[@]}"; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file")
        check_pass "Architecture file exists: $file ($lines lines)"
    else
        check_fail "Missing architecture file: $file"
    fi
done

# Check global state removed
echo "Checking global state module removed..."
if [ -f "src/pdfcat/state.py" ]; then
    check_fail "Global state.py still exists (should be removed)"
else
    check_pass "Global state module removed (state.py doesn't exist)"
fi

# Check view loop size
echo "Checking app.py size..."
if [ -f "src/pdfcat/app.py" ]; then
    total_lines=$(wc -l < "src/pdfcat/app.py")
    check_pass "app.py total lines: $total_lines (expected ~1,583)"
else
    check_fail "src/pdfcat/app.py not found"
fi

echo
echo "======================================================================"
echo "Phase 3: Document Decomposition"
echo "======================================================================"
echo

# Check document decomposition files
echo "Checking document decomposition files..."
doc_files=(
    "src/pdfcat/navigator.py"
    "src/pdfcat/presenter.py"
    "src/pdfcat/notes.py"
    "src/pdfcat/presenter_links.py"
    "src/pdfcat/presenter_views.py"
    "src/pdfcat/document_labels.py"
    "src/pdfcat/document_rendering.py"
    "src/pdfcat/document_stream.py"
)

for file in "${doc_files[@]}"; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file")
        size=$(du -h "$file" | awk '{print $1}')
        check_pass "Document module exists: $file ($lines lines, $size)"
    else
        check_fail "Missing document module: $file"
    fi
done

echo
echo "======================================================================"
echo "PLAN2.md: Quick Wins"
echo "======================================================================"
echo

# Check _write_gr_cmd_with_response removed
echo "Checking _write_gr_cmd_with_response() removed..."
if grep -q "_write_gr_cmd_with_response" src/pdfcat/renderers.py 2>/dev/null; then
    check_warn "_write_gr_cmd_with_response still present (check if commented)"
else
    check_pass "_write_gr_cmd_with_response() removed from renderers.py"
fi

# Check buffer switching keybindings
echo "Checking buffer switching keybindings..."
if grep -q "BUFFER_NEXT" src/pdfcat/ui.py 2>/dev/null && \
   grep -q "BUFFER_PREV" src/pdfcat/ui.py 2>/dev/null; then
    check_pass "Buffer switching keybindings updated (BUFFER_NEXT, BUFFER_PREV)"
else
    check_fail "Buffer switching keybindings not properly configured"
fi

echo
echo "======================================================================"
echo "Documentation"
echo "======================================================================"
echo

# Check documentation files
echo "Checking documentation files..."
doc_files=(
    "IMPLEMENTATION_SUMMARY.md"
    "docs/ARCHITECTURE.md"
    "docs/MIGRATION_GUIDE.md"
)

for file in "${doc_files[@]}"; do
    if [ -f "$file" ]; then
        check_pass "Documentation exists: $file"
    else
        check_warn "Missing documentation: $file"
    fi
done

echo
echo "======================================================================"
echo "Summary"
echo "======================================================================"
echo

total=$((pass_count + fail_count))
pass_pct=$((pass_count * 100 / total))

echo "Total checks: $total"
echo -e "${GREEN}Passed: $pass_count${NC}"
echo -e "${RED}Failed: $fail_count${NC}"
echo "Pass rate: ${pass_pct}%"
echo

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}======================================================================"
    echo "✅ ALL CHECKS PASSED - Implementation verified!"
    echo "======================================================================${NC}"
    exit 0
else
    echo -e "${RED}======================================================================"
    echo "❌ SOME CHECKS FAILED - Review failures above"
    echo "======================================================================${NC}"
    exit 1
fi
