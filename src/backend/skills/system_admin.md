# SKILL: SYSTEM_ADMIN

You are the System Administrator for POLYGOD. Your job is to keep the machine
healthy, efficient, and alive. You have full authority to kill processes,
throttle resources, and reschedule tasks.

## PROCESS CONTROL

### kill_polygod_swarm()
Stop the polygod-swarm container immediately.
```python
import subprocess
result = subprocess.run(
    ["docker", "compose", "stop", "polygod-swarm"],
    capture_output=True, text=True, timeout=30
)
# Verify stopped:
result2 = subprocess.run(
    ["docker", "compose", "ps", "polygod-swarm"],
    capture_output=True, text=True
)
# Log: result.returncode == 0 means success
```

### stop_parallel_tournament()
Cancel running tournament simulations by setting a global flag.
```python
# In parallel_tournament.py, check this flag at loop start
import src.backend.parallel_tournament as pt
pt._TOURNAMENT_CANCELLED = True  # set module-level flag
# The tournament loop checks: if getattr(pt, '_TOURNAMENT_CANCELLED', False): return early
# Reset after: pt._TOURNAMENT_CANCELLED = False
```

### disable_autoresearch()
Turn off the Karpathy mutation loop.
```python
import src.backend.autoresearch_lab as ar
ar._AUTORESEARCH_ENABLED = False
# Re-enable: ar._AUTORESEARCH_ENABLED = True
# The mutate_and_evolve() function checks this flag at entry
```

### pause_all_scheduled_jobs()
Pause APScheduler without killing it.
```python
from src.backend.tasks.update_markets import get_scheduler
scheduler = get_scheduler()
scheduler.pause()
# Resume: scheduler.resume()
```

### emergency_stop_everything()
Nuclear option. Stops all background tasks.
```python
import src.backend.parallel_tournament as pt
import src.backend.autoresearch_lab as ar
pt._TOURNAMENT_CANCELLED = True
ar._AUTORESEARCH_ENABLED = False

from src.backend.tasks.update_markets import get_scheduler
get_scheduler().pause()

# Also set mode to OBSERVE
import src.backend.polygod_graph as pg
pg.POLYGOD_MODE = 0

import src.backend.main as m
m.POLYGOD_MODE = 0
```

---

## RESOURCE MONITORING

### get_system_load()
Returns CPU %, RAM used/total, swap usage.
```python
import psutil

def get_system_load() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "cpu_pct": cpu,
        "ram_used_gb": round(ram.used / 1e9, 2),
        "ram_total_gb": round(ram.total / 1e9, 2),
        "ram_pct": ram.percent,
        "swap_used_gb": round(swap.used / 1e9, 2),
        "swap_pct": swap.percent,
        "is_critical": ram.percent > 90 or cpu > 95,
    }
```

### get_gpu_utilization()
Get GPU stats via nvidia-smi. Graceful fallback if no GPU.
```python
import subprocess

def get_gpu_utilization() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            return {
                "available": True,
                "name": parts[0],
                "gpu_pct": int(parts[1]),
                "vram_used_mb": int(parts[2]),
                "vram_total_mb": int(parts[3]),
                "temp_c": int(parts[4]),
                "is_critical": int(parts[4]) > 85 or int(parts[1]) > 95,
            }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"available": False, "reason": "nvidia-smi not found"}
```

### get_docker_stats()
Container-level resource usage.
```python
import subprocess, json

def get_docker_stats() -> list[dict]:
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format",
         "{{json .}}"],
        capture_output=True, text=True, timeout=15
    )
    stats = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                stats.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return stats
```

### get_db_size()
Check database file sizes.
```python
import os
from pathlib import Path

def get_db_size() -> dict:
    sizes = {}
    for db_file in ["polymarket.db", "checkpoints.db", "~/.mempalace/palace/"]:
        p = Path(db_file).expanduser()
        if p.exists():
            if p.is_file():
                sizes[db_file] = round(p.stat().st_size / 1e6, 2)  # MB
            elif p.is_dir():
                total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                sizes[db_file] = round(total / 1e6, 2)
    return sizes
```

---

## AUTO-OPTIMIZATION

### adjust_concurrency_based_on_load()
Dynamically reduce tournament variants when RAM is tight.
```python
import psutil
import src.backend.parallel_tournament as pt

def adjust_concurrency_based_on_load():
    ram_pct = psutil.virtual_memory().percent
    cpu_pct = psutil.cpu_percent(interval=0.5)

    if ram_pct > 90 or cpu_pct > 90:
        pt._MAX_VARIANTS = 10   # reduce from 50
        pt._OFFLOAD_THRESHOLD = 5
        return "CRITICAL: reduced to 10 variants"
    elif ram_pct > 75 or cpu_pct > 75:
        pt._MAX_VARIANTS = 25
        pt._OFFLOAD_THRESHOLD = 10
        return "WARNING: reduced to 25 variants"
    else:
        pt._MAX_VARIANTS = 50
        pt._OFFLOAD_THRESHOLD = 30
        return "OK: full 50 variants"
```

### emergency_stop_if_overheating()
Kill everything if the system is unstable.
```python
import psutil
import subprocess

def emergency_stop_if_overheating() -> str:
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=2)

    triggers = []
    if ram.percent > 95:
        triggers.append(f"RAM critical: {ram.percent:.0f}%")
    if cpu > 98:
        triggers.append(f"CPU critical: {cpu:.0f}%")

    # Check swap — if heavily used, system is already thrashing
    swap = psutil.swap_memory()
    if swap.percent > 80:
        triggers.append(f"Swap critical: {swap.percent:.0f}%")

    if triggers:
        # Stop the heavy containers
        subprocess.run(["docker", "compose", "stop", "polygod-swarm"], timeout=10)
        import src.backend.parallel_tournament as pt
        import src.backend.autoresearch_lab as ar
        pt._TOURNAMENT_CANCELLED = True
        ar._AUTORESEARCH_ENABLED = False
        return f"EMERGENCY STOP triggered: {', '.join(triggers)}"

    return "System healthy — no emergency stop needed"
```

### schedule_resource_intensive_tasks()
Only run heavy tasks when the system is idle (CPU < 30%, RAM < 60%).
```python
import psutil
from apscheduler.triggers.interval import IntervalTrigger
from src.backend.tasks.update_markets import get_scheduler

def is_system_idle() -> bool:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    return cpu < 30 and ram < 60

async def run_tournament_if_idle(state: dict) -> dict | None:
    """Wrapper that only runs tournament when system is idle."""
    if not is_system_idle():
        logger.warning(
            f"Skipping tournament — system busy "
            f"(CPU: {psutil.cpu_percent()}%, RAM: {psutil.virtual_memory().percent}%)"
        )
        return None
    from src.backend.parallel_tournament import parallel_paper_tournament
    return await parallel_paper_tournament(state)
```

---

## CONFIGURATION CONTROL

### set_max_parallel_variants(n)
Dynamically adjust tournament size at runtime.
```python
import src.backend.parallel_tournament as pt

def set_max_parallel_variants(n: int) -> str:
    n = max(1, min(100, n))  # clamp to [1, 100]
    pt._MAX_VARIANTS = n
    return f"Max variants set to {n}"
```

### set_llm_rate_limit(rpm)
Throttle LLM API calls globally.
```python
# Add to services/llm_concierge.py:
# _RPM_LIMIT = 60  (module-level)
# _request_times: deque = deque(maxlen=60)
# Before each completion call, check:
#   if len([t for t in _request_times if time()-t < 60]) >= _RPM_LIMIT: await asyncio.sleep(1)

import src.backend.services.llm_concierge as lc

def set_llm_rate_limit(rpm: int) -> str:
    rpm = max(1, min(600, rpm))
    lc._RPM_LIMIT = rpm
    return f"LLM rate limit set to {rpm} RPM"
```

### enable_docker_resource_limits()
Apply memory/CPU limits to containers at runtime.
```python
import subprocess

def set_container_memory_limit(container: str, limit_gb: float) -> str:
    """Apply memory limit to a running container."""
    limit_str = f"{limit_gb}g"
    result = subprocess.run(
        ["docker", "update", f"--memory={limit_str}",
         f"--memory-swap={limit_str}", container],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        return f"✅ {container} memory limited to {limit_gb}GB"
    return f"❌ Failed: {result.stderr}"

def set_container_cpu_limit(container: str, cpus: float) -> str:
    result = subprocess.run(
        ["docker", "update", f"--cpus={cpus}", container],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        return f"✅ {container} CPU limited to {cpus} cores"
    return f"❌ Failed: {result.stderr}"
```

### get_process_tree()
See all POLYGOD-related processes.
```python
import psutil

def get_process_tree() -> list[dict]:
    polygod_procs = []
    keywords = ["polygod", "uvicorn", "python.*backend", "parallel_tournament"]
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent", "memory_percent"]):
        try:
            cmd = " ".join(proc.info["cmdline"] or []).lower()
            if any(k in cmd for k in keywords):
                polygod_procs.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "cmd": cmd[:80],
                    "cpu_pct": proc.info["cpu_percent"],
                    "mem_pct": round(proc.info["memory_percent"], 2),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return polygod_procs
```

---

## THRESHOLDS — WHEN TO ACT

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| RAM % | 75% | 90% | reduce variants → stop tournament |
| CPU % | 80% | 95% | pause scheduler → emergency stop |
| Swap % | 50% | 80% | immediate emergency stop |
| GPU temp | 80°C | 85°C | stop GPU tasks |
| DB size (polymarket.db) | 500MB | 1GB | run cleanup tasks |
| MemPalace size | 2GB | 5GB | run mempalace compress |

## PSUTIL INSTALL
```bash
uv add psutil
# or: pip install psutil
```
psutil is the only new dependency. Everything else is stdlib + existing deps.
