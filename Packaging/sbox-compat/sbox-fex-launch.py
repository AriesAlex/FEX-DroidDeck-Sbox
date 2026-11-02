#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Run DroidDeck's maintained launcher with this tool's isolated FEX binaries."""
import os
from pathlib import Path
import runpy
import sys

COMPAT_ENV = {
    "DOTNET_INTERNAL_ThreadSuspendInjection": "0",
    "DOTNET_EnableWriteXorExecute": "0",
    "FEX_TSOENABLED": "1",
    "FEX_VECTORTSOENABLED": "1",
    "FEX_MEMCPYSETTSOENABLED": "1",
    "FEX_HALFBARRIERTSOENABLED": "0",
    "FEX_X87REDUCEDPRECISION": "0",
}


def load_backend(tool_dir):
    tool_dir = Path(tool_dir).resolve()
    prefix = tool_dir / "fex"
    for name in ("FEX", "FEXServer"):
        if not os.access(prefix / "bin" / name, os.X_OK):
            raise RuntimeError(f"Missing executable: {prefix / 'bin' / name}")

    namespace = runpy.run_path("/usr/local/bin/droiddeck-fex")
    # runpy returns a dictionary copy; functions execute against their original globals.
    backend = namespace["main"].__globals__
    original_install = backend["fex_install"]
    original_guest_environment = backend["guest_environment"]

    def fex_install():
        original = original_install()
        if original is None:
            raise RuntimeError("DroidDeck's matching FEX runtime/thunks are unavailable")
        return dict(original, bin=str(prefix / "bin" / "FEX"),
                    server=str(prefix / "bin" / "FEXServer"), portable=False)

    def data_dir(env):
        runtime = env.get("XDG_RUNTIME_DIR", "")
        if runtime and len(runtime) < 50 and os.path.isdir(runtime) and os.access(runtime, os.W_OK):
            return os.path.join(runtime, "fex-sbox-compat")
        return f"/tmp/fex-sbox-compat-{os.getuid()}"

    def guest_environment(info, env):
        result = original_guest_environment(info, env)
        # Apply after DroidDeck's shared/per-game settings so this tool keeps its tested mode.
        result.update(COMPAT_ENV)
        result.setdefault("DOTNET_GCRegionRange", "800000000")
        result["PATH"] = str(prefix / "bin") + os.pathsep + result.get("PATH", os.defpath)
        return result

    backend.update(
        fex_install=fex_install,
        guest_environment=guest_environment,
        data_dir=data_dir,
        CONFIG_DIR=str(tool_dir / "state" / "config"),
        DATA_DIR=str(tool_dir / "state" / "data"),
        CACHE_DIR=str(tool_dir / "state" / "cache"),
        STATUS_FILE=str(tool_dir / "state" / "status.json"),
        # This tool has a fixed, manually installed build; never invoke the global updater.
        update_own_fex=lambda: None,
    )
    return backend


def main(argv):
    if argv[:1] == ["--memory-guard-child"]:
        return load_backend(Path(__file__).resolve().parent)["main"](argv[1:])
    if argv[:1] == ["steam"]:
        from memory_guard import run_guarded
        return run_guarded([sys.executable, __file__, "--memory-guard-child", *argv],
                           Path(__file__).resolve().parent / "state/memory-guard.log")
    return load_backend(Path(__file__).resolve().parent)["main"](argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
