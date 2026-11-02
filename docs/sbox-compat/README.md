# Experimental S&box / CoreCLR compatibility build

This local fork is based on FEX-2610 (`14c92681f4d62cf84d901460e0358de09c8847a7`).
It preserves DroidDeck's four FEX r8 compatibility patches and adds narrowly
adapted Linux signal corrections. It does not fix arbitrary signal-handler
GPR edits at an unchanged guest RIP. CoreCLR needs the runtime option below.
S&box testing remains in progress; reaching its loading screen is not a claim
of a stable playable session.

## Build manually on Linux ARM64

The tested host used Ubuntu/DroidDeck ARM64, Clang 21.1.8, CMake 4.2.3, Ninja
1.13.2, lld, libxxhash-dev, pkg-config, and the pinned Git submodules. Install
these dependencies using the host package manager, then run:

```sh
./Scripts/build-sbox-local.sh /absolute/build-directory /absolute/isolated-prefix
```

`FEX_BUILD_JOBS` defaults to 2. `CC` and `CXX` override the Clang executables.
The script reproduces the tested CMake switches and builds FEX, FEXServer, and
FEXGetConfig; it does not use `cmake --install` or replace the system FEX.
Existing compatible thunks are linked from `/usr/local` by default; change
`FEX_EXISTING_THUNK_PREFIX` if necessary. This is a native ARM64 build recipe,
not an x86-64-to-ARM64 cross-compilation recipe.

Changing build paths or compiler versions can change binary hashes. The script
reproduces the tested source and flags; it does not promise bit-identical output.

GitHub workflow files have been removed from this fork branch. Builds and
release uploads are manual.

## Install the Steam compatibility tool manually

```sh
python3 Scripts/install-sbox-compat.py /absolute/isolated-prefix \
  "$HOME/.local/share/Steam/compatibilitytools.d/.sbox-fex-compat"
```

The installer adapts the current DroidDeck `droiddeck-fex-tool` wrapper and
preserves its GPU, taskset and SteamVR handling. The Python entry point loads
`/usr/local/bin/droiddeck-fex` with `runpy`, replaces `fex_install` in the actual
function globals, and retains the maintained runtime/thunk setup logic. The
binary and server come from this isolated tool; final guest environment values
are applied after shared/per-game configuration. `DOTNET_GCRegionRange` keeps
the shared value, with `800000000` as the fallback.

Configuration, cache, status and server IPC are separate for this tool. Its
launcher skips the global FEX updater. It does not edit the original FEX or
DroidDeck launcher, select a Steam mapping, or restart Steam. Existing tool
installations are backed up under Steam's `sbox-fex-compat-backups` directory,
outside the compatibility-tool discovery directory.

The hidden directory name is required on DroidDeck. Steam discovers the tool
there normally, while DroidDeck's automatic Proton adoption skips hidden
folders. A visible directory is rewritten as Windows/Proton at session startup,
which prevents the native Linux launch. Keep the internal tool ID below unchanged.
If upgrading an older visible installation, close Steam, move that directory to
`.sbox-fex-compat`, restore its original Linux manifests with the installer, and
restart Steam. Do not keep both directories registered.

A [reference fix for DroidDeck's registration helper](droiddeck-preserve-linux-tools.patch)
also records the underlying bug. Editing the installed helper alone is temporary:
DroidDeck reinstalls it when rebuilding the environment, so the hidden directory
is the persistent installation method used here.

Installed tool ID: `sbox-fex-compat`.
Display name: `S&box FEX (signal compatibility)`.

## Tested runtime settings

```sh
export DOTNET_GCRegionRange=800000000
export DOTNET_EnableWriteXorExecute=0
export DOTNET_INTERNAL_ThreadSuspendInjection=0
export FEX_TSOENABLED=1
export FEX_VECTORTSOENABLED=1
export FEX_MEMCPYSETTSOENABLED=1
export FEX_HALFBARRIERTSOENABLED=0
export FEX_X87REDUCEDPRECISION=0
```

`DOTNET_GCRegionRange` is parsed as hexadecimal by CoreCLR. The suspend-injection
option disables PAL signal injection for suspension; normal collection still
runs, using cooperative opportunities. A CPU-bound managed loop without safe
points can delay suspension, so real application behavior requires validation.
The standalone stress runs also used `DOTNET_PROCESSOR_COUNT=2`.

Three complete 20-pass stress runs passed with injection disabled. The counted
run allocated 1,510,370,208 bytes and completed 374 Gen0, 152 Gen1 and 16 Gen2
collections. Without the injection option, this same FEX build still crashed
in the stress test. `NoGCRegion` and startup hooks were not used for these runs.
The HalfBarrier=1 variant also passed one run; it is not a stricter TSO mode.

## Changes and provenance

The baseline imports these four patches unchanged from
[Droid-Deck/DroidDeck at c5577478caab6af7efc9fa806a706ef49ad6ca2a](https://github.com/Droid-Deck/DroidDeck/tree/c5577478caab6af7efc9fa806a706ef49ad6ca2a/tools/fex/patches):

- `0001-openat2-enosys-fallback.patch`
- `0002-thunkgen-newer-clang.patch`
- `0003-allocator32-map32bit-exhaustion.patch`
- `0004-auxv-at-platform.patch`

Signal changes are adapted from StonkGuy's
[patch series](https://github.com/StonkGuy/eac-arm64-emulation-poc/blob/master/docs/patches.md):

| Patch | StonkGuy/FEX commit | Behavior |
| --- | --- | --- |
| 0007 | `00146a422aea5e55d356dda7f78dfdc8d758e41d` | Linux guest handler masks; optional tracing/config omitted |
| 0008 | `0267762a46a4f4da1675e9169d5ffba3e09fbc4e` | Clear syscall spill state before a guest handler |
| 0018 | `12dd3ebf59e9ef9d19487e1fbc32f70658f826c3` | XSAVE state size and trailer |
| 0020 | `0a9cd24f5038e3035b5430da4cc950056569aa18` | Populate/read x86-64 `uc_sigmask` |
| 0041 | `3a9ca6b154acc5f0fc792ff0e4a6ccd6e2eb90fa` | Restore interrupted `InSyscallInfo` on every signal return |

The local adaptation also writes the restored mask to the host return ucontext,
removing FEX-required signals from that host mask. This keeps the mask installed
by Linux consistent with the guest-visible mask when the guest handler edits
`uc_sigmask`. The ia32 path restores its saved mask but does not gain support
for guest edits to the ia32 signal-frame mask. Signal-handler GPR edits with
unchanged RIP remain an existing limitation.

Code is unchanged from the successfully tested binary. Review checked mask
widening/restoration, removal of unmaskable signals, preservation of FEX-required
host signals, separate C++-syscall spill state, and AVX/non-AVX frame sizing.
Pending-signal re-raising follows the source patch's ordering. No new CPU tests
were run during final source packaging.

## Attribution and license notices

FEX and the StonkGuy/FEX source retain the upstream MIT license and copyright
notice in the repository's `LICENSE` (Ryan Houdek, 2019). Original signal-patch
author: StonkGuy <68372320+StonkGuy@users.noreply.github.com>. The source commit
messages retain additional coauthor attribution. The imported patches are not
claimed as original work by this fork's local integration author.

DroidDeck's source repository provides GNU GPL version 3 text. Its original
license is retained in `licenses/DroidDeck-LICENSE.txt`; the imported baseline's
source location is above. This notice records provenance without relabeling
those third-party changes as newly authored MIT code. Preserve both upstream
and imported-source notices alongside any distributed source or binaries.

This is an explicitly authorized user fork/local experiment, not an upstream
FEX contribution. The inherited upstream `AGENTS.md` is retained.
