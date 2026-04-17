"""
POLYGOD System Administrator — Runtime process and resource control.

This module provides the actual Python implementations of all system_admin.md
functions. Import from here; the skill file describes them in human-readable form.
"""

import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Module-level control flags ────────────────────────────────────────────────
# These are checked at loop entry in respective modules
_TOURNAMENT_CANCELLED: bool = False
_AUTORESEARCH_ENABLED: bool = True
_MAX_VARIANTS: int = 50
_OFFLOAD_THRESHOLD: int = 30
_RPM_LIMIT: int = 60


# ── Process Control ────────────────────────────────────────────────────────────


async def kill_polygod_swarm() -> dict:
    """Stop the polygod-swarm container."""
    try:
        result = subprocess.run(
            ["docker", "compose", "stop", "polygod-swarm"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        ok = result.returncode == 0
        return {
            "success": ok,
            "message": "polygod-swarm stopped" if ok else result.stderr,
        }
    except Exception as e:
        logger.error(f"kill_polygod_swarm failed: {e}")
        return {"success": False, "message": str(e)}


def stop_parallel_tournament() -> str:
    """Cancel any running tournament simulations."""
    global _TOURNAMENT_CANCELLED
    _TOURNAMENT_CANCELLED = True
    # Also propagate to the actual module
    try:
        import src.backend.parallel_tournament as pt

        pt._TOURNAMENT_CANCELLED = True
    except ImportError:
        pass
    return "Tournament cancellation flag set — active runs will stop at next checkpoint"


def resume_parallel_tournament() -> str:
    """Re-enable tournaments after stopping them."""
    global _TOURNAMENT_CANCELLED
    _TOURNAMENT_CANCELLED = False
    try:
        import src.backend.parallel_tournament as pt

        pt._TOURNAMENT_CANCELLED = False
    except ImportError:
        pass
    return "Tournament cancellation cleared — tournaments enabled"


def disable_autoresearch() -> str:
    """Disable the Karpathy mutation loop."""
    global _AUTORESEARCH_ENABLED
    _AUTORESEARCH_ENABLED = False
    try:
        import src.backend.autoresearch_lab as ar

        ar._AUTORESEARCH_ENABLED = False
    except ImportError:
        pass
    return "AutoResearch disabled — no more strategy mutations"


def enable_autoresearch() -> str:
    """Re-enable the Karpathy mutation loop."""
    global _AUTORESEARCH_ENABLED
    _AUTORESEARCH_ENABLED = True
    try:
        import src.backend.autoresearch_lab as ar

        ar._AUTORESEARCH_ENABLED = True
    except ImportError:
        pass
    return "AutoResearch enabled"


def emergency_stop_everything() -> dict:
    """Nuclear option — halt all background tasks, set mode 0."""
    results = {}

    # Stop tournament
    results["tournament"] = stop_parallel_tournament()

    # Stop autoresearch
    results["autoresearch"] = disable_autoresearch()

    # Pause scheduler
    try:
        from src.backend.tasks.update_markets import get_scheduler

        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.pause()
            results["scheduler"] = "paused"
        else:
            results["scheduler"] = "already stopped"
    except Exception as e:
        results["scheduler"] = f"error: {e}"

    # Set mode to OBSERVE
    try:
        import src.backend.main as m
        import src.backend.polygod_graph as pg

        pg.POLYGOD_MODE = 0
        m.POLYGOD_MODE = 0
        results["mode"] = "set to 0 (OBSERVE)"
    except Exception as e:
        results["mode"] = f"error: {e}"

    logger.critical("EMERGENCY STOP executed: %s", results)
    return results


# ── Resource Monitoring ────────────────────────────────────────────────────────


def get_system_load() -> dict:
    """CPU, RAM, swap usage."""
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu_pct": cpu,
            "ram_used_gb": round(ram.used / 1e9, 2),
            "ram_total_gb": round(ram.total / 1e9, 2),
            "ram_pct": ram.percent,
            "swap_used_gb": round(swap.used / 1e9, 2),
            "swap_pct": swap.percent,
            "disk_used_gb": round(disk.used / 1e9, 2),
            "disk_total_gb": round(disk.total / 1e9, 2),
            "disk_pct": disk.percent,
            "is_critical": ram.percent > 90 or cpu > 95 or swap.percent > 80,
            "warnings": _build_resource_warnings(
                cpu, ram.percent, swap.percent, disk.percent
            ),
        }
    except ImportError:
        return {"error": "psutil not installed — run: uv add psutil"}


def _build_resource_warnings(
    cpu: float, ram: float, swap: float, disk: float
) -> list[str]:
    warnings = []
    if cpu > 95:
        warnings.append(f"CPU CRITICAL: {cpu:.0f}%")
    elif cpu > 80:
        warnings.append(f"CPU high: {cpu:.0f}%")
    if ram > 90:
        warnings.append(f"RAM CRITICAL: {ram:.0f}%")
    elif ram > 75:
        warnings.append(f"RAM high: {ram:.0f}%")
    if swap > 80:
        warnings.append(f"SWAP CRITICAL: {swap:.0f}%")
    elif swap > 50:
        warnings.append(f"Swap elevated: {swap:.0f}%")
    if disk > 90:
        warnings.append(f"DISK CRITICAL: {disk:.0f}%")
    return warnings


def get_gpu_utilization() -> dict:
    """GPU stats via nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            temp = int(parts[4])
            gpu_pct = int(parts[1])
            return {
                "available": True,
                "name": parts[0],
                "gpu_pct": gpu_pct,
                "vram_used_mb": int(parts[2]),
                "vram_total_mb": int(parts[3]),
                "temp_c": temp,
                "is_critical": temp > 85 or gpu_pct > 95,
                "warnings": [
                    *([f"GPU CRITICAL: {gpu_pct}%"] if gpu_pct > 95 else []),
                    *([f"GPU HOT: {temp}°C"] if temp > 85 else []),
                ],
            }
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"nvidia-smi error: {e}")
    return {"available": False}


def get_docker_stats() -> list[dict]:
    """Container resource usage."""
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        stats = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    stats.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return stats
    except Exception as e:
        return [{"error": str(e)}]


def get_process_tree() -> list[dict]:
    """All POLYGOD-related processes."""
    try:
        import psutil

        keywords = [
            "polygod",
            "uvicorn",
            "backend",
            "parallel_tournament",
            "autoresearch",
        ]
        procs = []
        for proc in psutil.process_iter(
            ["pid", "name", "cmdline", "cpu_percent", "memory_percent", "status"]
        ):
            try:
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
                if any(k in cmd for k in keywords) and "skill" not in cmd:
                    procs.append(
                        {
                            "pid": proc.info["pid"],
                            "name": proc.info["name"],
                            "cmd": cmd[:100],
                            "cpu_pct": round(proc.info["cpu_percent"] or 0, 1),
                            "mem_pct": round(proc.info["memory_percent"] or 0, 2),
                            "status": proc.info["status"],
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return procs
    except ImportError:
        return [{"error": "psutil not installed"}]


# ── Auto-Optimization ──────────────────────────────────────────────────────────


def adjust_concurrency_based_on_load() -> str:
    """Reduce tournament variants when RAM/CPU are high."""
    global _MAX_VARIANTS, _OFFLOAD_THRESHOLD
    try:
        import psutil

        ram_pct = psutil.virtual_memory().percent
        cpu_pct = psutil.cpu_percent(interval=0.5)

        if ram_pct > 90 or cpu_pct > 90:
            _MAX_VARIANTS = 10
            _OFFLOAD_THRESHOLD = 5
            msg = f"CRITICAL (RAM:{ram_pct:.0f}% CPU:{cpu_pct:.0f}%) → variants=10"
        elif ram_pct > 75 or cpu_pct > 75:
            _MAX_VARIANTS = 25
            _OFFLOAD_THRESHOLD = 10
            msg = f"WARNING (RAM:{ram_pct:.0f}% CPU:{cpu_pct:.0f}%) → variants=25"
        else:
            _MAX_VARIANTS = 50
            _OFFLOAD_THRESHOLD = 30
            msg = f"OK (RAM:{ram_pct:.0f}% CPU:{cpu_pct:.0f}%) → variants=50"

        # Propagate to tournament module
        try:
            import src.backend.parallel_tournament as pt

            pt._MAX_VARIANTS = _MAX_VARIANTS
        except ImportError:
            pass

        logger.info(f"Concurrency adjusted: {msg}")
        return msg
    except ImportError:
        return "psutil not available — cannot adjust concurrency"


async def emergency_stop_if_overheating() -> str:
    """Kill heavy tasks if system is unstable."""
    try:
        import psutil

        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=2)
        swap = psutil.swap_memory()

        triggers = []
        if ram.percent > 95:
            triggers.append(f"RAM:{ram.percent:.0f}%")
        if cpu > 98:
            triggers.append(f"CPU:{cpu:.0f}%")
        if swap.percent > 80:
            triggers.append(f"SWAP:{swap.percent:.0f}%")

        if not triggers:
            return "System healthy"

        reason = f"Emergency stop — {', '.join(triggers)}"
        logger.critical(reason)

        # Stop heavy containers
        subprocess.run(
            ["docker", "compose", "stop", "polygod-swarm"],
            timeout=10,
            capture_output=True,
        )

        # Set flags
        stop_parallel_tournament()
        disable_autoresearch()

        # Send Telegram alert
        try:
            from src.backend.skills.alert_rules import send_alert

            await send_alert(reason, priority="high")
        except Exception:
            pass

        return reason
    except ImportError:
        return "psutil not available"


# ── Configuration Control ──────────────────────────────────────────────────────


def set_max_parallel_variants(n: int) -> str:
    """Dynamically adjust tournament size."""
    global _MAX_VARIANTS
    n = max(1, min(200, n))
    _MAX_VARIANTS = n
    try:
        import src.backend.parallel_tournament as pt

        pt._MAX_VARIANTS = n
    except ImportError:
        pass
    return f"Max parallel variants set to {n}"


def set_llm_rate_limit(rpm: int) -> str:
    """Throttle LLM API calls per minute."""
    global _RPM_LIMIT
    rpm = max(1, min(600, rpm))
    _RPM_LIMIT = rpm
    try:
        import src.backend.services.llm_concierge as lc

        lc._RPM_LIMIT = rpm
    except ImportError:
        pass
    return f"LLM rate limit set to {rpm} RPM"


def set_container_resource_limit(
    container: str,
    memory_gb: float | None = None,
    cpus: float | None = None,
) -> dict:
    """Apply memory/CPU limits to a running Docker container."""
    results = {}

    if memory_gb is not None:
        limit = f"{memory_gb}g"
        r = subprocess.run(
            [
                "docker",
                "update",
                f"--memory={limit}",
                f"--memory-swap={limit}",
                container,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        results["memory"] = "ok" if r.returncode == 0 else r.stderr.strip()

    if cpus is not None:
        r = subprocess.run(
            ["docker", "update", f"--cpus={cpus}", container],
            capture_output=True,
            text=True,
            timeout=10,
        )
        results["cpus"] = "ok" if r.returncode == 0 else r.stderr.strip()

    return results


# ── Health Report ──────────────────────────────────────────────────────────────


async def full_health_report() -> dict:
    """Complete system health snapshot."""
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": get_system_load(),
        "gpu": get_gpu_utilization(),
        "docker": get_docker_stats(),
        "processes": get_process_tree(),
        "flags": {
            "tournament_cancelled": _TOURNAMENT_CANCELLED,
            "autoresearch_enabled": _AUTORESEARCH_ENABLED,
            "max_variants": _MAX_VARIANTS,
            "rpm_limit": _RPM_LIMIT,
        },
    }

    # Add POLYGOD-specific checks
    try:
        from src.backend.tasks.update_markets import get_scheduler

        report["scheduler_running"] = get_scheduler().running
    except Exception:
        report["scheduler_running"] = False

    try:
        import src.backend.main as m

        report["polygod_mode"] = m.POLYGOD_MODE
    except Exception:
        report["polygod_mode"] = -1

    # Overall health verdict
    sys_load = report["system"]
    is_critical = isinstance(sys_load, dict) and sys_load.get("is_critical", False)
    report["overall"] = "CRITICAL" if is_critical else "OK"

    return report
