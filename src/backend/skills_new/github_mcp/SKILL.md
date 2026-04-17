---
name: github-mcp
description: GitHub operations using GitHub MCP. Use when users ask to create issues, submit pull requests, push code fixes, manage repositories, review code, or automate GitHub workflows.
---

# GitHub MCP Skill

An expert agent for GitHub operations using GitHub MCP tools.

## Capabilities

- **Issue Management**: Create, update, close, and manage GitHub issues
- **Pull Request Operations**: Create PRs, review, merge, and manage
- **Code Push**: Push commits, create branches, manage remote
- **Repository Management**: Create repos, manage settings, handle teams
- **Code Review**: Review code changes, add comments, approve/reject
- **Workflow Automation**: Trigger actions, manage CI/CD pipelines

## GitHub MCP Tools

### Repository Operations
- `github_create_repository` - Create a new repository
- `github_get_repository` - Get repository details
- `github_update_repository` - Update repository settings
- `github_delete_repository` - Delete a repository
- `github_list_repositories` - List user/organization repos

### Issue Operations
- `github_create_issue` - Create a new issue
- `github_get_issue` - Get issue details
- `github_update_issue` - Update an issue
- `github_close_issue` - Close an issue
- `github_add_issue_comment` - Add comment to issue
- `github_list_issues` - List repository issues

### Pull Request Operations
- `github_create_pull_request` - Create a PR
- `github_get_pull_request` - Get PR details
- `github_update_pull_request` - Update PR
- `github_merge_pull_request` - Merge a PR
- `github_list_pull_requests` - List PRs
- `github_add_pull_request_review` - Submit PR review

### Code & Branch Operations
- `github_create_branch` - Create a new branch
- `github_delete_branch` - Delete a branch
- `github_list_branches` - List repository branches
- `github_get_file` - Get file contents
- `github_create_or_update_file` - Create/update file
- `github_delete_file` - Delete a file

### Commit Operations
- `github_create_commit` - Create a commit
- `github_list_commits` - List repository commits
- `github_get_commit` - Get commit details

## Workflow Examples

### Create Issue
```python
github_create_issue(
    owner="username",
    repo="project-name",
    title="Bug: Login fails on mobile",
    body="Steps to reproduce...",
    labels=["bug", "high-priority"]
)
```

### Create Pull Request
```python
github_create_pull_request(
    owner="username",
    repo="project-name",
    title="Fix: Resolve login issue",
    head="feature-branch",
    base="main",
    body="This PR fixes the login issue..."
)
```

### Push Code Fix
```python
github_create_or_update_file(
    owner="username",
    repo="project-name",
    path="src/fix.py",
    message="fix: resolve login bug",
    content=open("fix.py").read(),
    branch="main"
)
```

### Review Pull Request
```python
github_add_pull_request_review(
    owner="username",
    repo="project-name",
    pull_number=123,
    event="APPROVE",
    body="LGTM! Great fix."
)
```

## Best Practices

### Issue Management
- Use descriptive titles with clear context
- Add labels for categorization
- Include steps to reproduce for bugs
- Link related issues

### Pull Requests
- Use conventional commit messages
- Reference related issues (#123)
- Keep PRs focused and small
- Add comprehensive descriptions

### Code Reviews
- Be constructive and specific
- Suggest improvements with examples
- Approve when ready to merge

## Output Format

Provide:
1. Operation performed (issue/PR/commit/branch)
2. Resource identifier (number, SHA, name)
3. Summary of changes
4. Links to affected resources
