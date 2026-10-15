#!/bin/sh
# make client (P0.10): Release build of the unmodified client (native arm64 on Apple silicon),
# then record where cuo landed in runs/client-path (gitignored) for make play.
set -eu
cd "$(dirname "$0")/../.."
dotnet build src/ClassicUO.Client/ClassicUO.Client.csproj -c Release
cuo=$(find bin/Release -name cuo -type f | head -n 1)
if [ -z "$cuo" ]; then
  echo "client: build finished but no cuo under bin/Release"
  exit 1
fi

# ClassicUO ships cuoapi.dll (the old plugin API) marked x64-only, and an arm64 .NET process
# refuses it: "Could not load file or assembly 'cuoapi'" on the first frame. Its code is IL only,
# so mark the copy in bin/ as arm64. external/cuoapi stays untouched. Found 2026-10-15 (P0.10).
api="$(dirname "$cuo")/cuoapi.dll"
if [ "$(uname -m)" = "arm64" ] && [ -f "$api" ]; then
  python3 - "$api" <<'PY'
import struct, sys
path = sys.argv[1]
data = bytearray(open(path, "rb").read())
pe = struct.unpack_from("<I", data, 0x3C)[0]
if data[pe:pe + 4] != b"PE\0\0":
    sys.exit("client: cuoapi.dll is not a PE file; not changed")
machine = struct.unpack_from("<H", data, pe + 4)[0]
if machine == 0x8664:
    struct.pack_into("<H", data, pe + 4, 0xAA64)
    open(path, "wb").write(data)
    print("client: marked cuoapi.dll for arm64 (it shipped x64-only)")
elif machine == 0xAA64:
    print("client: cuoapi.dll already marked for arm64")
else:
    sys.exit(f"client: unexpected machine 0x{machine:04x} in cuoapi.dll; not changed")
PY
fi

mkdir -p runs
printf '%s\n' "$(pwd)/$cuo" > runs/client-path
echo "client: $cuo (path written to runs/client-path)"
