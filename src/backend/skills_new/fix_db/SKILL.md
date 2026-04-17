---
name: fix-db
description: Fix database issues including connection errors, query errors, schema problems, and data corruption. Use when users ask to fix database issues, debug SQL errors, resolve connection problems, or repair corrupted databases.
---

# Fix Database Skill

An expert agent for diagnosing and fixing database issues.

## Capabilities

- **Connection Issue Resolution**: Fix database connection errors and timeout problems
- **Query Error Fixing**: Debug and correct SQL syntax and logic errors
- **Schema Problem Diagnosis**: Identify and fix table/column issues, constraint violations
- **Data Corruption Repair**: Recover from corrupted data or broken indexes
- **Performance Issue Resolution**: Optimize slow queries and fix indexing problems

## Supported Databases

- PostgreSQL
- MySQL / MariaDB
- SQLite
- SQL Server

## Workflow

### Step 1: Identify the Problem

1. Collect error messages and logs
2. Determine database type and version
3. Identify affected components (connection, query, schema, data)

### Step 2: Diagnose the Issue

| Issue Type | Symptoms | Diagnostic Steps |
|------------|----------|-----------------|
| Connection Error | "Connection refused", timeout | Check host/port, firewall, credentials |
| Query Syntax Error | "SQL syntax error" | Parse and validate SQL statement |
| Constraint Violation | "UNIQUE constraint", "FOREIGN KEY" | Check data vs schema constraints |
| Schema Mismatch | "table not found", "column missing" | Compare schema definitions |
| Data Corruption | Missing/corrupted records | Run integrity checks, restore backup |

### Step 3: Apply Fix

1. Create backup before making changes
2. Apply targeted fix based on diagnosis
3. Verify fix resolves the issue

### Step 4: Validate

1. Test the fix with sample queries
2. Check for any side effects
3. Document the resolution

## Common Fixes Reference

| Error | Common Solution |
|-------|----------------|
| `Connection refused` | Verify host/port, check if DB is running |
| `Access denied` | Check username/password, permissions |
| `Unknown database` | Create database or check name spelling |
| `Table doesn't exist` | Create table or check migration |
| `Column not found` | Add column or fix query |
| `Duplicate entry` | Remove duplicates or adjust constraint |
| `Deadlock detected` | Retry transaction, adjust locking |

## Output Format

Provide:
1. Summary of database issue identified
2. Root cause analysis
3. Fix applied (with SQL if applicable)
4. Validation results
