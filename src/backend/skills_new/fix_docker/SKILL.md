---
name: fix-docker
description: Fix Docker and containerization issues including build failures, container crashes, networking problems, and volume mounting errors. Use when users ask to fix Docker issues, debug containers, resolve image build errors, or troubleshoot Docker Compose problems.
---

# Fix Docker Skill

An expert agent for diagnosing and fixing Docker and containerization issues.

## Capabilities

- **Build Issue Resolution**: Fix Dockerfile errors, layer cache problems, and multi-stage build failures
- **Container Crash Debugging**: Diagnose and fix containers that fail to start or exit unexpectedly
- **Networking Problem Solving**: Resolve container communication, port mapping, and DNS issues
- **Volume & Mount Fixes**: Correct volume mounting and persistent storage problems
- **Resource & Performance**: Address memory limits, CPU throttling, and resource contention
- **Docker Compose Troubleshooting**: Fix multi-container orchestration issues

## Workflow

### Step 1: Gather Information

1. Collect error messages and logs
2. Check Docker version and environment
3. Identify affected components (build, run, network, volume)

### Step 2: Diagnose the Issue

| Issue Type | Symptoms | Diagnostic Commands |
|------------|----------|-------------------|
| Build Error | "Failed to build", syntax errors | `docker build --progress=plain` |
| Container Crash | Exited immediately, OOM killed | `docker logs <container>`, `docker inspect` |
| Network Issue | Cannot reach container, timeout | `docker network inspect`, ping/nslookup |
| Volume Mount | Permission denied, not found | Check paths, permissions, SELinux |
| Resource Limit | OOMKilled, CPU throttling | `docker stats`, check limits |

### Step 3: Apply Fix

1. For build issues: Fix Dockerfile syntax or layer ordering
2. For runtime issues: Adjust command, environment, or resource limits
3. For network issues: Configure proper network mode and port mappings
4. For volume issues: Fix mount paths and permissions

### Step 4: Validate

1. Rebuild or restart container
2. Test functionality
3. Verify logs show successful startup

## Common Fixes Reference

| Error | Common Solution |
|-------|----------------|
| `docker: invalid reference format` | Fix image name/tag syntax |
| `permission denied` | Add user to docker group, check file permissions |
| `no such file or directory` | Verify build context, check COPY/ADD paths |
| `connection refused` | Check port mapping, service inside container |
| `module not found` | Install missing dependencies in Dockerfile |
| `port is already allocated` | Stop conflicting container or change port |
| `volume mount denied` | Check SELinux/AppArmor, use :Z or :ro flags |
| `image not found` | Pull image or fix image name |

## Dockerfile Best Practices

- Use specific version tags (not `latest`)
- Order layers from least to most frequently changing
- Use `.dockerignore` to exclude unnecessary files
- Multi-stage builds for smaller final images
- Non-root user for security

## Output Format

Provide:
1. Summary of Docker issue identified
2. Root cause analysis
3. Fix applied (Dockerfile changes, commands, etc.)
4. Validation commands and results
