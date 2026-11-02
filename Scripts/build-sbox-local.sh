#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
sbox_source=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
sbox_build=${1:-"$sbox_source/out-sbox/build"}
sbox_prefix=${2:-"$sbox_source/out-sbox/install"}
case $(uname -m) in aarch64|arm64) ;; *) printf '%s\n' 'This script reproduces the native Linux ARM64 build; use an ARM64 host/toolchain.' >&2; exit 1 ;; esac
mkdir -p -- "$sbox_build" "$sbox_prefix"
sbox_build=$(cd -- "$sbox_build" && pwd)
sbox_prefix=$(cd -- "$sbox_prefix" && pwd)
git -C "$sbox_source" submodule update --init --recursive
cmake -S "$sbox_source" -B "$sbox_build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$sbox_prefix" \
  -DCMAKE_C_COMPILER="${CC:-clang-21}" -DCMAKE_CXX_COMPILER="${CXX:-clang++-21}" \
  -DCMAKE_CXX_FLAGS=-g1 -DUSE_LINKER=lld -DTUNE_CPU=none -DTUNE_ARCH=armv8-a \
  -DBUILD_TESTING=OFF -DBUILD_FEXCONFIG=OFF -DBUILD_THUNKS=OFF \
  -DENABLE_ASSERTIONS=OFF -DENABLE_LTO=OFF -DENABLE_CCACHE=OFF \
  -DENABLE_OFFLINE_TELEMETRY=OFF
cmake --build "$sbox_build" --target FEX FEXServer FEXGetConfig --parallel "${FEX_BUILD_JOBS:-2}"
install -d -- "$sbox_prefix/bin" "$sbox_prefix/share/licenses/fex-sbox"
install -m 0755 -- "$sbox_build/Bin/FEX" "$sbox_build/Bin/FEXServer" "$sbox_build/Bin/FEXGetConfig" "$sbox_prefix/bin/"
install -m 0644 -- "$sbox_source/LICENSE" "$sbox_source/docs/sbox-compat/README.md" "$sbox_prefix/share/licenses/fex-sbox/"
install -m 0644 -- "$sbox_source/docs/sbox-compat/licenses/DroidDeck-LICENSE.txt" "$sbox_prefix/share/licenses/fex-sbox/"
# The tested build reused DroidDeck's matching FEX-2610 r8 thunks.
# No system files are installed or overwritten.
sbox_thunk_prefix=${FEX_EXISTING_THUNK_PREFIX:-/usr/local}
for sbox_subdir in share lib; do
  if [ -d "$sbox_thunk_prefix/$sbox_subdir/fex-emu" ] && [ ! -e "$sbox_prefix/$sbox_subdir/fex-emu" ]; then
    mkdir -p -- "$sbox_prefix/$sbox_subdir"
    ln -s -- "$sbox_thunk_prefix/$sbox_subdir/fex-emu" "$sbox_prefix/$sbox_subdir/fex-emu"
  fi
done
sha256sum "$sbox_prefix/bin/FEX" "$sbox_prefix/bin/FEXServer" "$sbox_prefix/bin/FEXGetConfig"
printf 'Built isolated binaries in %s\n' "$sbox_prefix/bin"
