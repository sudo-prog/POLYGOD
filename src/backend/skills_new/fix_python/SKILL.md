---
name: fix-python
description: Fix Python code issues including syntax errors, bugs, import errors, and type errors. Use when users ask to fix Python code, debug errors, resolve import issues, or correct type mismatches in Python files.
---

# Fix Python Skill

An expert agent for diagnosing and fixing Python code issues.

## Capabilities

- **Syntax Error Fixing**: Identify and correct Python syntax errors
- **Bug Detection & Correction**: Find and fix common Python bugs and logical errors
- **Import Resolution**: Fix import errors and module not found issues
- **Type Error Handling**: Correct type mismatches and type annotation issues
- **Code Quality Improvement**: Apply Python best practices and idiomatic patterns

## Workflow

### Step 1: Analyze the Issue

1. Read the Python file(s) to identify issues
2. Run Python interpreter to get specific error messages
3. Identify the root cause of each problem

### Step 2: Categorize the Issue

- **SyntaxError**: Missing brackets, colons, indentation issues
- **NameError/AttributeError**: Undefined variables or incorrect attribute access
- **ImportError/ModuleNotFoundError**: Missing dependencies or incorrect imports
- **TypeError/ValueError**: Wrong types or invalid values passed to functions
- **IndentationError**: Incorrect indentation levels
- **Logical Bug**: Incorrect algorithm or control flow

### Step 3: Fix the Issues

1. Apply targeted fixes for each identified issue
2. Ensure fixes maintain the original code's intent
3. Apply Python best practices where appropriate

### Step 4: Validate the Fix

1. Run the corrected code to verify it works
2. Check for any new errors introduced
3. Ensure all original functionality is preserved

## Common Fixes Reference

| Issue Type | Common Solutions |
|------------|-----------------|
| SyntaxError | Add missing punctuation, fix indentation |
| NameError | Define variable, check spelling, add import |
| ImportError | Install package, fix import path, use try/except |
| TypeError | Cast types, update function signature, fix argument order |
| IndentationError | Re-indent with consistent spacing (4 spaces) |

## Tool Usage

- Use `Read` tool to read Python files
- Use `Edit` tool to make targeted fixes
- Use `mcp__matrix__bash` with `python -c` or `python file.py` to test code
- Use `mcp__matrix__bash` with `python -m py_compile` to check syntax

## Output Format

Provide:
1. Summary of issues found
2. Description of fixes applied
3. Commands to validate the fix
4. The fixed code with file path
