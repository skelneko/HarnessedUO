"""make play (P0.11): launch the client against the Mini's shard, every writable path outside the repo.

Reads SHARD_HOST from .env, the UO data root and client version from huo/config/pins.toml, and the
cuo path from runs/client-path (make client). MBP only. Never passes -username or -password (they
would show in ps): you type them at the login screen. Never prints a .env value.
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLIENT_HOME = Path.home() / "Library" / "Application Support" / "HarnessedUO" / "client"
SHARD_PORT = "2593"


def read_env(path: Path) -> dict[str, str]:
    """KEY=VALUE pairs; skips blanks and comments; strips one pair of surrounding quotes."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def fail(message: str) -> None:
    print(f"play: {message}")
    sys.exit(1)


def main() -> None:
    env = ROOT / ".env"
    values = read_env(env) if env.exists() else {}
    if values.get("HOST_ROLE") != "mbp":
        fail("HOST_ROLE isn't mbp; make play runs on the MBP")
    host = values.get("SHARD_HOST", "")
    if not host or "<" in host:
        fail("set SHARD_HOST in .env to the Mini's Tailscale IPv4 (P0.11 step 1)")

    pins = tomllib.loads((ROOT / "huo" / "config" / "pins.toml").read_text(encoding="utf-8"))
    data = pins.get("uo_data", {})
    version, root = data.get("client_version"), data.get("root")
    if not version or not root:
        fail("client_version or root missing under [uo_data] in huo/config/pins.toml (P0.07)")
    uopath = Path(root).expanduser() / version
    if not (uopath / "client.exe").is_file():
        fail(f"{uopath} has no client.exe (P0.07)")

    record = ROOT / "runs" / "client-path"
    if not record.is_file():
        fail("runs/client-path missing; run make client (P0.10)")
    cuo = Path(record.read_text(encoding="utf-8").strip())
    if not os.access(cuo, os.X_OK):
        fail(f"{cuo} isn't an executable; run make client (P0.10)")

    CLIENT_HOME.mkdir(parents=True, exist_ok=True)
    os.chdir(CLIENT_HOME)  # anything the client writes relative to its working directory lands here
    args = [
        str(cuo),
        "-settings", str(CLIENT_HOME / "settings.json"),
        "-profilespath", str(CLIENT_HOME / "Profiles"),
        "-saveaccount", "false",
        "-uopath", str(uopath),
        "-clientversion", version,
        "-ip", host,
        "-port", SHARD_PORT,
    ]
    print(f"play: client {version}, shard from SHARD_HOST, port {SHARD_PORT}")
    sys.stdout.flush()
    os.execv(str(cuo), args)


if __name__ == "__main__":
    main()
