---
name: filesystem-mcp
description: Read and write codebase files directly using Filesystem MCP. Use when users ask to read files, write files, edit code, create directories, or perform filesystem operations on the local codebase.
---

# Filesystem MCP Skill

An expert agent for reading, writing, and managing codebase files using Filesystem MCP tools.

## Capabilities

- **File Reading**: Read files from any location in the codebase
- **File Writing**: Create new files or overwrite existing ones
- **File Editing**: Make targeted edits to specific sections
- **Directory Management**: Create, list, and manage directories
- **Search Operations**: Find files and content within the codebase
- **Batch Operations**: Perform multiple file operations efficiently

## Filesystem MCP Tools

### File Operations
- `filesystem_read_file` - Read file contents with optional line range
- `filesystem_write_file` - Write content to a file (create or overwrite)
- `filesystem_edit_file` - Edit specific sections of a file
- `filesystem_copy_file` - Copy files to new locations
- `filesystem_move_file` - Move/rename files
- `filesystem_delete_file` - Delete files

### Directory Operations
- `filesystem_create_directory` - Create new directories
- `filesystem_delete_directory` - Delete directories
- `filesystem_list_directory` - List directory contents
- `filesystem_list_directory_recursive` - List contents recursively

### Search Operations
- `filesystem_search_files` - Search for files by pattern
- `filesystem_search_content` - Search for content within files
- `filesystem_get_file_info` - Get file metadata

## Workflow

### Reading Files

```python
# Read entire file
filesystem_read_file(path="/path/to/file.py")

# Read specific lines (1-indexed, inclusive)
filesystem_read_file(path="/path/to/file.py", start_line=10, end_line=50)

# Read with offset and limit
filesystem_read_file(path="/path/to/file.py", offset=100, limit=50)
```

### Writing Files

```python
# Write content (creates if not exists, overwrites if exists)
filesystem_write_file(
    path="/path/to/new_file.py",
    content="#!/usr/bin/env python3\nprint('Hello, World!')"
)
```

### Editing Files

```python
# Edit specific section (old_str must be unique)
filesystem_edit_file(
    path="/path/to/file.py",
    old_str="old_content = 'value'",
    new_str="new_content = 'updated_value'"
)
```

## Best Practices

### Before Writing
- **Always read the file first** if it exists
- Verify file path is correct
- Check for backup if overwriting

### For Edits
- Ensure `old_str` is unique in the file
- Include surrounding context for reliable matching
- Verify the edit was applied correctly

### Directory Operations
- Create parent directories as needed
- Check directory exists before writing
- Use recursive options for nested structures

## Common Operations

| Task | Tool | Example |
|------|------|---------|
| Read config | `read_file` | Read JSON, YAML, TOML configs |
| Update code | `edit_file` | Change function implementations |
| Create file | `write_file` | Create new modules, tests |
| Find files | `search_files` | `*.py`, `*.tsx` patterns |
| Search code | `search_content` | Find function definitions |

## Safety Guidelines

- **Read-only preferred** when possible
- Verify paths before destructive operations
- Create backups for critical files
- Use `list_directory` to check before creating

## Output Format

Provide:
1. Operation performed (read/write/edit/delete)
2. File path affected
3. Summary of changes made
4. Verification of operation success
