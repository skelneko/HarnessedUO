"""make doctor: one PASS/WARN/FAIL row per check for this clone and host.

Standard library only. Run with: uv run python huo/tools/doctor.py [--json] [--deep]
--deep also hashes every frozen UO data file against its manifest (slower).
Never prints a .env value, except HOST_ROLE (mbp or mini), which is not a secret.
Exits 1 if any row is FAIL, else 0.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "skelneko/HarnessedUO"
ENV_HOME = Path.home() / "Library" / "Application Support" / "HarnessedUO"
ROLES = ("mbp", "mini")
SHARD_PORT = 2593
MODERNUO = Path.home() / "src" / "ModernUO" / "Distribution"
PLACEHOLDER = re.compile(r"<[^<>]*>")
CRED_IN_URL = re.compile(r"://[^/@\s]+:[^/@\s]+@")

rows: list[dict] = []


def add(group: str, check: str, status: str, detail: str = "", hint: str = "") -> None:
    rows.append({"group": group, "check": check, "status": status, "detail": detail, "hint": hint})


def run(*cmd: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def out(*cmd: str) -> str | None:
    p = run(*cmd)
    if p is None or p.returncode != 0:
        return None
    return p.stdout.strip()


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


def read_example(path: Path) -> list[tuple[str, bool]]:
    """(key, optional) for each key in .env.example; '# optional' on the line marks it optional."""
    keys = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        keys.append((s.split("=", 1)[0].strip(), "# optional" in s))
    return keys


def check_tools(pins: dict) -> None:
    pin = pins.get("tools", {})
    uv = out("uv", "--version")  # "uv 0.12.23 (Homebrew ...)"
    versions = {
        "dotnet": ("dotnet_sdk", out("dotnet", "--version")),
        "gitleaks": ("gitleaks", out("gitleaks", "version")),
        "uv": ("uv", uv.split()[1] if uv and len(uv.split()) > 1 else None),
        "python": ("python", platform.python_version()),
    }
    for tool, (pin_key, found) in versions.items():
        want = pin.get(pin_key)
        if found is None:
            add("tools", tool, "FAIL", "not found on PATH", "run make deps (on the Mini, install as the Homebrew owner)")
        elif tool == "dotnet" and not found.startswith("10."):
            add("tools", tool, "FAIL", f"{found}, need major 10", "install .NET SDK 10 (dotnet-sdk cask)")
        elif want is None:
            add("tools", tool, "WARN", f"{found}, no pin", f"add {pin_key} under [tools] in huo/config/pins.toml")
        elif found != want:
            add("tools", tool, "WARN", f"{found}, pin {want}", "upgrade on both Macs the same day, then update the pins")
        else:
            add("tools", tool, "PASS", found)
    for tool in ("gh", "git"):
        if shutil.which(tool):
            add("tools", tool, "PASS", "on PATH")
        else:
            add("tools", tool, "FAIL", "not found on PATH", "run make deps")


def check_git() -> None:
    hooks = out("git", "config", "core.hooksPath")
    if hooks == ".githooks":
        add("git", "core.hooksPath", "PASS", ".githooks")
    else:
        add("git", "core.hooksPath", "FAIL", hooks or "unset", "run make hooks")

    fetch = out("git", "remote", "get-url", "upstream")
    push = out("git", "remote", "get-url", "--push", "upstream")
    if fetch is None:
        add("git", "upstream remote", "FAIL", "missing", "run make hooks")
    elif push != "DISABLED":
        add("git", "upstream remote", "FAIL", "push URL is not DISABLED", "run make hooks")
    else:
        add("git", "upstream remote", "PASS", "fetch-only, push DISABLED")

    # gh stores its default repo in git config (remote.<name>.gh-resolved); read that
    # directly, so the check works on a clone with no gh login (e.g. the Mini's station).
    resolved = out("git", "config", "--get-regexp", r"^remote\..*\.gh-resolved$") or ""
    entries = [line.split(None, 1) for line in resolved.splitlines() if line.strip()]
    ok = False
    if len(entries) == 1 and len(entries[0]) == 2:
        key, value = entries[0]
        remote = key[len("remote."):-len(".gh-resolved")]
        url = out("git", "remote", "get-url", remote) or ""
        ok = value == REPO or (value == "base" and re.search(r"github\.com[:/]" + REPO + r"(\.git)?$", url) is not None)
    if ok:
        add("git", "gh default repo", "PASS", REPO)
    else:
        detail = "unset" if not entries else ("set on several remotes" if len(entries) > 1 else "not " + REPO)
        add("git", "gh default repo", "FAIL", detail, "run make hooks")

    remotes = out("git", "remote", "-v") or ""
    leaky = sorted({line.split()[0] for line in remotes.splitlines() if CRED_IN_URL.search(line)})
    if leaky:
        add("git", "remote URLs", "FAIL", "credentials in URL of: " + ", ".join(leaky),
            "git remote set-url <name> https://github.com/<owner>/<repo>.git; gh keeps the token")
    else:
        add("git", "remote URLs", "PASS", "no credentials in URLs")


def check_env() -> dict[str, str]:
    env = ROOT / ".env"
    if not env.is_symlink():
        add(".env", "symlink", "FAIL", "missing" if not env.exists() else "regular file, not a link",
            "move it to ~/Library/Application Support/HarnessedUO/.env and symlink it (P0.03 step 1)")
        values = read_env(env) if env.exists() else {}
    else:
        target = Path(os.path.realpath(env))
        inside = str(target).startswith(str(ENV_HOME.resolve()) + os.sep)
        if not target.exists():
            add(".env", "symlink", "FAIL", "link target missing", "create the file in Application Support (P0.03 step 1)")
            values = {}
        elif not inside:
            add(".env", "symlink", "FAIL", "points outside Application Support/HarnessedUO", "relink it (P0.03 step 1)")
            values = read_env(target)
        else:
            mode = stat.S_IMODE(target.stat().st_mode)
            if mode & 0o077:
                add(".env", "symlink", "FAIL", f"link OK, mode {mode:o} (group/other can read)",
                    "chmod 600 ~/Library/Application\\ Support/HarnessedUO/.env")
            else:
                add(".env", "symlink", "PASS", f"into Application Support, mode {mode:o}")
            values = read_env(target)

    tracked = run("git", "ls-files", "--error-unmatch", ".env")
    if tracked is not None and tracked.returncode == 0:
        add(".env", "untracked", "FAIL", ".env is tracked by git", "git rm --cached .env, then rotate every secret in it")
    else:
        add(".env", "untracked", "PASS", "not tracked")

    example = ROOT / ".env.example"
    if not example.exists():
        add(".env", "keys", "FAIL", ".env.example missing", "restore .env.example (P0.02 step 6)")
        return values
    keys = read_example(example)
    unset = [k for k, _ in keys if k != "HOST_ROLE" and (not values.get(k) or PLACEHOLDER.search(values[k]))]
    n_set = sum(1 for k, _ in keys if values.get(k) and not PLACEHOLDER.search(values[k]))
    if unset:
        add(".env", "keys", "WARN", f"{n_set} of {len(keys)} set; not set yet: " + ", ".join(unset),
            "fill each when its session needs it (SHARD_HOST, UO_PLAYER_* P0.11; UO_GM_* P0.13; LLM_* P0.14)")
    else:
        add(".env", "keys", "PASS", f"{n_set} of {len(keys)} set")
    return values


def check_tree() -> None:
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        rel = Path(dirpath).relative_to(ROOT)
        if "Profiles" in dirnames:
            found.append(str(rel / "Profiles") + "/")
        if "settings.json" in filenames:
            found.append(str(rel / "settings.json"))
    if found:
        add("tree", "client state", "FAIL", "found: " + ", ".join(found[:5]),
            "delete them; always launch with -settings and -profilespath outside the repo")
    else:
        add("tree", "client state", "PASS", "no settings.json or Profiles/")


def check_host(values: dict[str, str]) -> None:
    role = values.get("HOST_ROLE", "")
    if role in ROLES:
        add("host", "HOST_ROLE", "PASS", role)
    else:
        add("host", "HOST_ROLE", "FAIL", "missing or not mbp|mini", "set HOST_ROLE=mbp or HOST_ROLE=mini in .env")


def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def check_uo_data(pins: dict, deep: bool) -> None:
    """Frozen UO data (P0.07): <root>/<client_version> from pins, owned by root, nothing writable, manifest complete."""
    data = pins.get("uo_data", {})
    version, root = data.get("client_version"), data.get("root")
    if not version or not root:
        add("data", "folder", "FAIL", "client_version or root not pinned", "set both under [uo_data] in huo/config/pins.toml (P0.07)")
        return
    folder = Path(root).expanduser() / version
    if not folder.is_dir():
        add("data", "folder", "FAIL", f"{folder} not found", "copy the frozen folder to this Mac (P0.07 steps 4-5)")
        return
    add("data", "folder", "PASS", str(folder))

    missing = [n for n in ("tiledata.mul", "client.exe") if not (folder / n).is_file()]
    if missing:
        add("data", "files", "FAIL", "missing: " + ", ".join(missing), "copy the frozen folder again (P0.07 steps 4-5)")
    else:
        add("data", "files", "PASS", "tiledata.mul, client.exe")

    on_disk: set[str] = set()
    writable = not_root = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        here = Path(dirpath)
        for p in [here] + [here / f for f in filenames]:
            st = p.lstat()
            writable += bool(st.st_mode & 0o222)
            not_root += st.st_uid != 0
        on_disk.update((here / f).relative_to(folder).as_posix() for f in filenames)
    if writable or not_root:
        add("data", "read-only", "FAIL", f"{writable} writable, {not_root} not owned by root",
            f"sudo chown -R root:wheel {folder}; sudo chmod -R a+rX,a-w {folder}")
    else:
        add("data", "read-only", "PASS", "owned by root, nothing writable")

    manifest = folder / "MANIFEST.sha256"
    if not manifest.is_file():
        add("data", "manifest", "FAIL", "MANIFEST.sha256 missing", "rebuild it on the PC (P0.07 step 2) and copy again")
        return
    text = manifest.read_bytes().decode("utf-8", errors="replace")
    listed: dict[str, str] = {}
    malformed = 0
    for line in text.split("\n"):
        digest, sep, rel = line.partition("  ")
        if sep and re.fullmatch(r"[0-9a-f]{64}", digest) and rel:
            listed[rel] = digest
        elif line.strip():
            malformed += 1
    on_disk.discard("MANIFEST.sha256")
    gone, extra = sorted(set(listed) - on_disk), sorted(on_disk - set(listed))
    problems = []
    if "\r" in text:
        problems.append("CRLF line endings (shasum -c needs LF)")
    if malformed:
        problems.append(f"{malformed} malformed lines")
    if gone:
        problems.append(f"{len(gone)} listed but missing, e.g. {gone[0]}")
    if extra:
        problems.append(f"{len(extra)} not listed, e.g. {extra[0]}")
    if not problems and deep:
        bad = [rel for rel, digest in sorted(listed.items()) if sha256_file(folder / rel) != digest]
        if bad:
            problems.append(f"{len(bad)} hash mismatches, e.g. {bad[0]}")
    if problems:
        add("data", "manifest", "FAIL", "; ".join(problems), "copy the frozen folder again (P0.07 steps 4-5); never edit it in place")
    elif deep:
        add("data", "manifest", "PASS", f"{len(listed)} files, all hashes match")
    else:
        add("data", "manifest", "PASS", f"{len(listed)} files present; hashes checked by make doctor-deep")


def exe_version(path: Path) -> str | None:
    """File version from a Windows exe's VS_FIXEDFILEINFO (signature 0xFEEF04BD after "VS_VERSION_INFO")."""
    data = path.read_bytes()
    start = data.find("VS_VERSION_INFO".encode("utf-16-le"))
    sig = data.find(b"\xbd\x04\xef\xfe", start) if start >= 0 else -1
    if sig < 0 or sig + 16 > len(data):
        return None
    ms, ls = struct.unpack_from("<II", data, sig + 8)
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def check_client_version(pins: dict) -> None:
    """P0.12: client.exe in the frozen folder carries the pinned client_version."""
    data = pins.get("uo_data", {})
    version, root = data.get("client_version"), data.get("root")
    exe = Path(root).expanduser() / version / "client.exe" if version and root else None
    if exe is None or not exe.is_file():
        return  # the data rows above already FAIL
    found = exe_version(exe)
    if found is None:
        add("data", "client version", "FAIL", "no version resource in client.exe", "copy the frozen folder again (P0.07)")
    elif found != version:
        add("data", "client version", "FAIL", f"client.exe is {found}, pin is {version}",
            "freeze the matching data (P0.07) or fix client_version in pins")
    else:
        add("data", "client version", "PASS", f"client.exe {found} = pin")


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def tilde(path: Path) -> str:
    home = str(Path.home())
    s = str(path)
    return "~" + s[len(home):] if s == home or s.startswith(home + os.sep) else s


def check_shard(values: dict[str, str]) -> None:
    """P0.09, Mini only: tmux session "shard" and port 2593; saves configured outside every repo."""
    if values.get("HOST_ROLE") != "mini":
        return
    listening = port_open(SHARD_PORT)
    if not MODERNUO.is_dir():
        # This account doesn't own the shard (e.g. huodev); it can only see the port.
        add("shard", "port 2593", "PASS" if listening else "WARN",
            "listening (shard runs under another account)" if listening else "not listening",
            "" if listening else "as station: make shard")
        return
    p = run("tmux", "has-session", "-t", "shard")
    session = p is not None and p.returncode == 0
    if session and listening:
        add("shard", "running", "PASS", "tmux session shard, port 2593 listening")
    else:
        add("shard", "running", "WARN",
            f"tmux session {'yes' if session else 'no'}, port 2593 {'listening' if listening else 'not listening'}",
            "make shard, then make shard-status")

    config = MODERNUO / "Configuration" / "modernuo.json"
    try:
        settings = json.loads(config.read_text(encoding="utf-8")).get("settings", {})
    except FileNotFoundError:
        add("shard", "save path", "FAIL", "modernuo.json missing", "first full start (P0.09 step 3)")
        return
    except (OSError, ValueError, AttributeError):
        add("shard", "save path", "FAIL", "modernuo.json unreadable", "check the file by hand")
        return
    raw = settings.get("world.savePath") if isinstance(settings, dict) else None
    if not raw:
        add("shard", "save path", "FAIL", "world.savePath not set", "set it in modernuo.json (P0.09 step 5)")
        return
    save = Path(raw).expanduser()
    if not save.is_absolute():
        save = MODERNUO / save
    save = save.resolve()
    repos = [ROOT.resolve(), MODERNUO.parent.resolve()]
    inside = [r for r in repos if save == r or r in save.parents]
    if inside:
        add("shard", "save path", "FAIL", f"{tilde(save)} is inside {tilde(inside[0])}",
            "set world.savePath to ~/uo-shard/main/saves (P0.09 step 5)")
    elif not save.is_dir():
        add("shard", "save path", "FAIL", f"{tilde(save)} missing", f"mkdir -p {tilde(save)}")
    else:
        add("shard", "save path", "PASS", f"{tilde(save)}, outside both repos")


def main() -> int:
    pins_path = ROOT / "huo" / "config" / "pins.toml"
    try:
        pins = tomllib.loads(pins_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        pins = {}
        add("tools", "pins.toml", "FAIL", type(e).__name__, "fix huo/config/pins.toml")
    check_tools(pins)
    check_git()
    values = check_env()
    check_tree()
    check_host(values)
    check_uo_data(pins, "--deep" in sys.argv[1:])
    check_client_version(pins)
    check_shard(values)

    if "--json" in sys.argv[1:]:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'STATUS':<6}  {'GROUP':<6}  {'CHECK':<16}  DETAIL")
        for r in rows:
            print(f"{r['status']:<6}  {r['group']:<6}  {r['check']:<16}  {r['detail']}")
            if r["status"] != "PASS" and r["hint"]:
                print(f"{'':<6}  {'':<6}  {'':<16}  hint: {r['hint']}")
        counts = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "WARN", "FAIL")}
        print(f"\n{counts['PASS']} PASS, {counts['WARN']} WARN, {counts['FAIL']} FAIL")
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
