# SPDX-License-Identifier: MIT
"""Stop only the launched process group before Android runs out of memory."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def memory_fields(path):
    return {key: int(value.split()[0]) for key, value in
            (line.split(":", 1) for line in Path(path).read_text().splitlines() if ":" in line)
            if value.strip().endswith(" kB")}


def run_guarded(command, log_path, limit_mb=6144, minimum_available_mb=1536):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", buffering=1) as log:
        def record(event, **values):
            log.write(json.dumps(dict(time=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                      event=event, **values)) + "\n")

        child = subprocess.Popen(command, start_new_session=True)
        requested_signal = None
        forwarded_at = None
        last_record = 0

        def forward(signum, frame):
            nonlocal requested_signal
            requested_signal = signum

        previous = {s: signal.signal(s, forward) for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
        try:
            record("started", pid=child.pid, limit_mb=limit_mb,
                   minimum_available_mb=minimum_available_mb)
            while child.poll() is None:
                if requested_signal is not None and forwarded_at is None:
                    os.killpg(child.pid, requested_signal)
                    forwarded_at = time.monotonic()
                try:
                    status = memory_fields(f"/proc/{child.pid}/status")
                    used_kb = status["VmRSS"] + status["VmSwap"]
                except (FileNotFoundError, KeyError):
                    if child.poll() is not None:
                        break
                    raise
                system = memory_fields("/proc/meminfo")
                available_kb = system["MemAvailable"]
                reason = ""
                if used_kb >= limit_mb * 1024:
                    reason = "process_memory_limit"
                elif available_kb < minimum_available_mb * 1024:
                    reason = "system_memory_reserve"
                elif forwarded_at is not None and time.monotonic() - forwarded_at > 3:
                    reason = "shutdown_timeout"
                if reason:
                    record("terminated", pid=child.pid, reason=reason,
                           rss_kb=status["VmRSS"], swap_kb=status["VmSwap"],
                           available_kb=available_kb)
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                    return 137
                if time.monotonic() - last_record >= 5:
                    record("sample", pid=child.pid, rss_kb=status["VmRSS"],
                           swap_kb=status["VmSwap"], available_kb=available_kb)
                    last_record = time.monotonic()
                time.sleep(0.25)
            record("exited", pid=child.pid, returncode=child.returncode)
            return child.returncode if child.returncode >= 0 else 128 - child.returncode
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            for signum, handler in previous.items():
                signal.signal(signum, handler)
