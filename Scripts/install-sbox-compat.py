#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Manually install an isolated Steam tool without selecting it or restarting Steam."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path, help="Manually built FEX prefix containing bin/FEX and bin/FEXServer")
    parser.add_argument("destination", type=Path, help="Steam compatibilitytools.d/.sbox-fex-compat directory")
    parser.add_argument("--droiddeck-tool", type=Path,
                        default=Path.home() / ".local/share/Steam/compatibilitytools.d/droiddeck-fex")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    prefix = args.prefix.resolve()
    destination = args.destination.absolute()
    if not destination.name.startswith("."):
        parser.error("Use a hidden destination such as .sbox-fex-compat so DroidDeck preserves this Linux tool")
    template = (args.droiddeck_tool / "droiddeck-fex-tool").read_text()
    if not template.startswith("#!/bin/bash\n"):
        parser.error("DroidDeck wrapper shell format changed; review before adapting")
    old = "/usr/local/bin/droiddeck-fex steam"
    if template.count(old) != 2:
        parser.error("DroidDeck wrapper layout changed; review its two launcher invocations before adapting")
    for name in ("FEX", "FEXServer", "FEXGetConfig"):
        if not os.access(prefix / "bin" / name, os.X_OK):
            parser.error(f"Missing executable: {prefix / 'bin' / name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".sbox-fex-stage-", dir=destination.parent))
    try:
        (staging / "fex/bin").mkdir(parents=True)
        for name in ("FEX", "FEXServer", "FEXGetConfig"):
            shutil.copy2(prefix / "bin" / name, staging / "fex/bin" / name)
        for subdir in ("lib", "share"):
            original = prefix / subdir / "fex-emu"
            if original.exists():
                target = staging / "fex" / subdir / "fex-emu"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(original.resolve())
        wrapper = template.replace("#!/bin/bash\n", '#!/bin/bash\ncompat_root=$(cd -- "$(dirname -- "$0")" && pwd)\n', 1)
        wrapper = wrapper.replace(old, '"$compat_root/sbox-fex-launch.py" steam')
        (staging / "sbox-fex-tool").write_text(wrapper)
        (staging / "sbox-fex-tool").chmod(0o755)
        shutil.copy2(source / "Packaging/sbox-compat/sbox-fex-launch.py", staging / "sbox-fex-launch.py")
        (staging / "sbox-fex-launch.py").chmod(0o755)
        (staging / "compatibilitytool.vdf").write_text('''"compatibilitytools"
{
  "compat_tools"
  {
    "sbox-fex-compat"
    {
      "install_path" "."
      "display_name" "S&box FEX (signal compatibility)"
      "from_oslist" "linux"
      "to_oslist" "linux"
    }
  }
}
''')
        (staging / "toolmanifest.vdf").write_text('''"manifest"
{
  "version" "2"
  "commandline" "/sbox-fex-tool %verb%"
  "use_tool_subprocess_reaper" "1"
}
''')
        shutil.copy2(source / "LICENSE", staging / "LICENSE")
        shutil.copytree(source / "docs/sbox-compat", staging / "provenance")
        hashes = {str(p.relative_to(staging)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in staging.rglob("*") if p.is_file() and not p.is_symlink()}
        (staging / "installed-files.sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
        subprocess.run(["bash", "-n", str(staging / "sbox-fex-tool")], check=True)
        compile((staging / "sbox-fex-launch.py").read_text(), "sbox-fex-launch.py", "exec")
        backup = None
        if destination.exists() or destination.is_symlink():
            backup_root = destination.parent.parent / "sbox-fex-compat-backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = backup_root / (destination.name + "-" + time.strftime("%Y%m%d-%H%M%S") + "-" + str(os.getpid()))
            destination.rename(backup)
        try:
            staging.rename(destination)
        except BaseException:
            if backup is not None:
                backup.rename(destination)
            raise
        print(json.dumps({"installed": str(destination), "backup": str(backup) if backup else None,
                          "steam_tool_selected": False, "steam_restarted": False}, indent=2))
    finally:
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == "__main__":
    main()
