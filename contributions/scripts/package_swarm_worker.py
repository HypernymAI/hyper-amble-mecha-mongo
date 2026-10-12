"""Build an allowlisted, credential-free worker ZIP for the Presents sandbox.

This copies only the worker's actual model-transport import closure. It never
reads runtime configuration, credentials, logs, memory, browser assets or Git.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "scripts/swarm_worker.py",
    "sandbox/__init__.py",
    "sandbox/provider.py",
    "bridges/__init__.py",
    "bridges/contract.py",
    "bridges/model_bridge.py",
    "amble_config.py",
    "amble_source_identity.py",
)
DEFAULT_OUTPUT = ROOT / "data" / "deliveries" / "presents-swarm-2026-10-11"
SECRET_PATTERNS = (
    re.compile(rb"\b(?:sk-ant-|sk-or-|sk-)[A-Za-z0-9_-]{16,}"),
    re.compile(rb"mongodb(?:\+srv)?://[^\s/:]+:[^\s@]+@"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"#token=[A-Za-z0-9_-]{16,}"),
)

MAC_LAUNCHER = '''#!/bin/zsh
set -u
cd -- "${0:A:h}" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if command -v python3 >/dev/null 2>&1; then
  python3 launch_worker.py
else
  print "Install Python 3.11 or newer, then open this file again."
fi
print "Press Return to close this window."
read -r worker_close
'''

PYTHON_LAUNCHER = '''"""Join the existing Presents town with this computer's own model account."""
from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
import shutil
import socket
import sys
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", help="Private join link from Nick; omit for a hidden prompt")
    parser.add_argument("--backend", choices=("claude-cli", "sol"))
    parser.add_argument("--name", default="chris-" + socket.gethostname())
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check imports and CLI presence without connecting")
    args = parser.parse_args()
    from sandbox import provider
    from bridges import model_bridge
    if args.check:
        print(json.dumps({"imports": "ok", "python": sys.version.split()[0],
                          "claude_cli": bool(shutil.which("claude")),
                          "codex_cli": bool(shutil.which("codex"))}))
        return
    backend = args.backend
    if backend is None:
        choice = input("Use your own Claude or Codex login? [claude/codex, default claude]: ").strip().lower()
        if choice not in ("", "claude", "codex"):
            raise SystemExit("Choose claude or codex, then launch again.")
        backend = "sol" if choice == "codex" else "claude-cli"
    cli = "codex" if backend == "sol" else "claude"
    if not shutil.which(cli):
        raise SystemExit("Install and sign in to " + cli + " on this computer first; no account is included in this package.")
    join_url = args.server or getpass.getpass("Paste Nick's complete private join link (hidden): ").strip()
    parsed = urlparse(join_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise SystemExit("Use the http(s) join link copied from Presents > Swarm > Setup.")
    if not parse_qs(parsed.fragment).get("token"):
        print("The link has no token; the worker will ask for the town access token separately.")
    from scripts.swarm_worker import main as run_worker
    sys.argv = ["swarm_worker.py", "--server", join_url, "--backend", backend, "--name", args.name]
    if args.once:
        sys.argv.append("--once")
    run_worker()


if __name__ == "__main__":
    main()
'''

WORKER_README = '''# Presents worker for Chris

This joins Nick's existing **AMBLE PRESENTS** city. It does not create another
app, copy a town, or include anyone's model login. Nick sends the private join
link separately. Opening that link in a browser is enough to visit, chat, view
homes, or import sandbox messages; running this worker is optional.

## macOS

1. Install Python 3.11 or newer and a current Claude Code CLI or Codex CLI.
   Sign in to that CLI with **your own account** and confirm it opens normally
   in Terminal. Keep the app signed in; never send your login files to Nick.
2. Unzip this folder, then double-click **Start Worker.command**. Choose Claude
   or Codex, and paste the complete private join link when asked. The hidden
   prompt keeps the link out of shell history.
3. Nick starts the swarm in Presents. The worker claims one available job at a
   time and prints the server's accepted or rejected receipt. Ctrl-C stops it.

If Finder will not execute the command, open Terminal in the extracted folder:

```sh
python3 launch_worker.py --check
python3 launch_worker.py --backend claude-cli --name chris-mac
# Or use your Codex login:
python3 launch_worker.py --backend sol --name chris-codex
```

Add `--once` for one submitted job attempt. While Nick has paused the town, the
worker waits for work; it does not start or unpause the host. A compatible CLI
is required: Claude's transport checks its isolation flags before inference.
No additional Python packages are needed for these two account-backed routes.

## Windows

Use WSL with Python 3.11+ and the model CLI installed and signed in **inside
WSL**. Extract this folder into WSL and run the same `python3 launch_worker.py`
command. The bridge uses Unix paths; native Windows is not supported by this
delivery. WSL and a second-machine connection have not been verified here.

## Connection and accounts

Use the exact link Nick copies from Presents > Swarm > Setup. It has the form
`http://HOST:3190/hypernym/presents/#token=PRIVATE_TOKEN` or an HTTPS address Nick
provides. A LAN address works only where that host is reachable; this package
does not configure a tunnel, router, VPN, or firewall. An internet connection
from Chris's computer remains unverified until Chris connects. The join token
grants shared town access, so keep the link private.

The worker sends its name and the model's reply to the town server. It sends
the leased fictional task, selected resident memories, and shared town context
to your chosen model provider using your local login. Model use consumes your
account's allowance. No model credentials are sent to the town server. The
Codex transport may use a temporary local copy of its own authentication file;
no authentication files are packaged or transferred between people.

If the terminal says `Worker retry`, check that the browser can reach Nick's
link, the CLI is signed in and current, and the account has available usage.
`--check` verifies imports and CLI presence only, not login or remote service
health. It makes no model request. The connection line alone is not proof of
an accepted job; look for an `ok: true` completion receipt in subsequent output.

## Browser and conversation import

Without running a worker, open the join link, choose a resident in Swarm, open
Memory, and use **Import sandbox conversation**. Choose `import-example.json`
as a format example and replace its toy text with messages intended for this
sandbox. The file may be an array of `{role, text}` objects or an object with
a `messages` array. Roles are `user`, `assistant`, or `system`; maximum 100
messages per import, 18,000 characters each, and 100,000 bytes per request.
Import stores memory only; it does not create job receipts, wages, or purchases.
Do not export private source conversations merely to populate this toy town.

The host stores world state and per-resident conversation memory locally.
Atlas synchronization depends on the host's valid database credentials and
network access; this delivery does not establish or verify it. Local embeddings
use an already-cached model when available; otherwise recall is lexical.
Health in Swarm Setup reports the current retrieval and connection status.

## Contents and verification

Only allowlisted Python worker/transport source, this guide, two launchers, an
import example, and a SHA-256 manifest are included. There is no server, site,
town database, memory, `.env`, account file, credential, or owner transcript.
The source is readable. Syntax/import/package checks are local checks, not
proof of remote inference or Chris-to-host connectivity.
'''

IMPORT_EXAMPLE = {"messages": [
    {"role": "user", "text": "In this fictional town, I like quiet reading corners."},
    {"role": "assistant", "text": "I will keep a reading corner in mind for my home."},
]}


def build(output: Path) -> dict:
    payloads = {}
    for name in SOURCES:
        path = ROOT / name
        if path.is_symlink() or path.resolve() != ROOT / name or not path.is_file():
            raise ValueError("Expected regular allowlisted source: " + name)
        payloads[name] = path.read_bytes()
    payloads.update({"launch_worker.py": PYTHON_LAUNCHER.encode(),
                     "Start Worker.command": MAC_LAUNCHER.encode(),
                     "README.md": WORKER_README.encode(),
                     "import-example.json": (json.dumps(IMPORT_EXAMPLE, indent=2) + "\n").encode()})
    for name, content in payloads.items():
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise ValueError("Secret-shaped material found; refusing package: " + name)
        if name.endswith(".py"):
            ast.parse(content.decode(), filename=name)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())}
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    manifest = {"format": "presents-worker/1", "source_files": list(SOURCES), "files": hashes,
                "scope": "worker only; no runtime state or credentials", "package_fingerprint": fingerprint}
    payloads["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ("presents-swarm-worker-" + fingerprint[:12] + ".zip")
    if not archive.exists():
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as packed:
            for name, content in sorted(payloads.items()):
                info = zipfile.ZipInfo("presents-swarm-worker/" + name, date_time=(2026, 10, 11, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | (0o755 if name.endswith(".command") else 0o644)) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                packed.writestr(info, content)
    with zipfile.ZipFile(archive) as packed:
        expected = {"presents-swarm-worker/" + name for name in payloads}
        if set(packed.namelist()) != expected or packed.testzip():
            raise ValueError("Archive file allowlist or CRC verification failed")
        for name, content in payloads.items():
            if packed.read("presents-swarm-worker/" + name) != content:
                raise ValueError("Archive content verification failed: " + name)
    return {"archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "files": len(payloads), "bytes": archive.stat().st_size,
            "checks": ["exact file allowlist", "source and launcher syntax", "secret-pattern scan", "ZIP CRC", "byte-for-byte content"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))


if __name__ == "__main__":
    main()
